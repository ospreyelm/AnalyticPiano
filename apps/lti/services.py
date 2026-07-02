"""
Tool-side LTI configuration: adapts LtiPlatform DB rows into pylti1p3's
registration/deployment interface, the readiness gate that decides whether
a launch may proceed past the "waiting on institutional sign-off" page,
identity resolution (Phase 4) mapping a validated launch onto a Django
User, and grade passback (Phase 6) via LTI Advantage's Assignment and
Grade Services (AGS).
"""
from __future__ import annotations

import functools
import hashlib

from django.conf import settings
from django.contrib.auth import get_user_model
from pylti1p3.assignments_grades import AssignmentsGradesService
from pylti1p3.deployment import Deployment
from pylti1p3.exception import LtiException
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.registration import Registration
from pylti1p3.service_connector import ServiceConnector
from pylti1p3.tool_config import ToolConfAbstract

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER
from apps.lti.models import LtiLineItem, LtiPlatform, LtiUserLink

User = get_user_model()


@functools.lru_cache(maxsize=1)
def get_tool_keypair() -> tuple[str, str]:
    """
    Return (private_pem, public_pem) for HarmonyLab's own LTI signing
    identity -- one keypair shared across every connected institution's
    registration, not one per platform.

    Reads LTI_TOOL_PRIVATE_KEY / LTI_TOOL_PUBLIC_KEY from settings (env-
    backed, same pattern as SECRET_KEY). Production must set these as
    stable secrets before any real LtiPlatform goes live: an ephemeral
    fallback key would change on every process restart, silently
    invalidating every platform's cached copy of HarmonyLab's JWKS.
    """
    private_pem = getattr(settings, "LTI_TOOL_PRIVATE_KEY", "") or ""
    public_pem = getattr(settings, "LTI_TOOL_PUBLIC_KEY", "") or ""
    if private_pem and public_pem:
        return private_pem, public_pem

    # Dev/test fallback only -- generated once per process, not persisted.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def build_registration(platform: LtiPlatform) -> Registration:
    """
    Adapt one LtiPlatform row into pylti1p3's Registration interface.
    Shared by ToolConfig (launch-time registration lookup) and the grade
    passback helpers below (which need a Registration to sign AGS service
    calls outside of any live launch).
    """
    private_key, public_key = get_tool_keypair()
    registration = Registration()
    registration.set_issuer(platform.issuer)
    registration.set_client_id(platform.client_id)
    registration.set_key_set_url(platform.jwks_url)
    registration.set_auth_token_url(platform.auth_token_url)
    registration.set_auth_login_url(platform.auth_login_url)
    registration.set_auth_audience(platform.auth_token_url)
    registration.set_tool_private_key(private_key)
    registration.set_tool_public_key(public_key)
    return registration


class ToolConfig(ToolConfAbstract):
    """
    Adapts LtiPlatform rows into pylti1p3's Registration/Deployment
    interface. One row per institution (see LtiPlatform docstring) --
    onboarding a second college or a high school is a new row, not a code
    change here.
    """

    def find_registration_by_issuer(self, iss, *args, **kwargs) -> Registration:
        platform = LtiPlatform.objects.filter(issuer=iss).first()
        if platform is None:
            raise LtiException(f"Unknown issuer: {iss}")
        return build_registration(platform)

    def find_registration_by_params(self, iss, client_id, *args, **kwargs) -> Registration:
        platform = LtiPlatform.objects.filter(issuer=iss, client_id=client_id).first()
        if platform is None:
            raise LtiException(f"Unknown issuer/client_id: {iss} / {client_id}")
        return build_registration(platform)

    def find_deployment(self, iss, deployment_id):
        platform = LtiPlatform.objects.filter(issuer=iss).first()
        if platform is None or deployment_id not in (platform.deployment_ids or []):
            return None
        return Deployment().set_deployment_id(deployment_id)

    def find_deployment_by_params(self, iss, deployment_id, client_id, *args, **kwargs):
        platform = LtiPlatform.objects.filter(issuer=iss, client_id=client_id).first()
        if platform is None or deployment_id not in (platform.deployment_ids or []):
            return None
        return Deployment().set_deployment_id(deployment_id)


def get_platform_for_launch(message_launch) -> LtiPlatform:
    """Re-resolve the LtiPlatform row a validated launch belongs to."""
    return LtiPlatform.objects.get(issuer=message_launch.get_iss())


def check_launch_allowed(platform: LtiPlatform) -> bool:
    """
    The all-or-nothing readiness gate: may this platform serve a real
    launch right now?

    Isolated on purpose: a future finer-grained version -- e.g. letting an
    institution's admin do connectivity testing before their data-sharing
    agreement is signed, without touching student data -- should only have
    to change this one function, not every call site.
    """
    return platform.is_ready_for_real_courses


def resolve_role(message_launch) -> str:
    """Instructor/TA -> teacher-side landing, everything else -> student."""
    if message_launch.check_teacher_access() or message_launch.check_teaching_assistant_access():
        return ROLE_TEACHER
    return ROLE_STUDENT


def _synthetic_email(platform: LtiPlatform, sub: str) -> str:
    """
    A unique, non-deliverable placeholder email for launches where the
    institution didn't release a real email claim (e.g. an anonymous-mode
    launch). ``.invalid`` is reserved by RFC 2606 for exactly this: no mail
    server exists for it, so even a guessed address can't receive a
    password-reset email -- direct signup/login can't claim this account
    that way, on top of it having no usable password to begin with.
    """
    digest = hashlib.sha256(f"{platform.pk}:{sub}".encode("utf-8")).hexdigest()[:24]
    return f"lti-{digest}@lti.harmonylab.invalid"


def resolve_user(message_launch, platform: LtiPlatform) -> User:
    """
    Resolve (creating if necessary) the Django User for a validated launch.

    ``sub`` is the only identity claim this requires -- it must work
    correctly under an institution's strictest ("anonymous") LTI
    configuration, where name/email claims are absent. See the identity
    resolution section of
    docs/superpowers/specs/2026-07-02-student-dashboard-lti-design.md.

    A newly created LTI-provisioned User always gets an unusable password:
    it can never be logged into directly, only reached via a fresh, valid
    LTI launch tied to the same (platform, sub) pair.
    """
    jwt_body = message_launch.get_launch_data()
    sub = jwt_body.get("sub")
    if not sub:
        raise LtiException("Launch is missing sub")

    link = (
        LtiUserLink.objects.filter(platform=platform, sub=sub)
        .select_related("user")
        .first()
    )
    if link is not None:
        return link.user

    email = jwt_body.get("email")
    email = User.objects.normalize_email(email).lower() if email else _synthetic_email(platform, sub)

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": jwt_body.get("given_name") or "",
            "last_name": jwt_body.get("family_name") or "",
            "role": resolve_role(message_launch),
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    LtiUserLink.objects.create(user=user, platform=platform, sub=sub)
    return user


# ---------------------------------------------------------------------------
# Grade passback (Phase 6)
# ---------------------------------------------------------------------------
#
# AGS access (the "lineitems"/"lineitem" URLs and granted scopes) is only
# available from inside a live, validated MessageLaunch -- there's no way
# to ask a platform "give me your AGS endpoint" out of band. So a launch
# that grants grade-passback scope has its AGS endpoint captured once
# (record_ags_endpoint, called from launch_view) and persisted on the
# student's LtiUserLink, which is what lets publish_score() work later,
# outside the request/response cycle of that original launch -- e.g. when
# called from an exercise submission handler.
#
# Whether publish_score() should actually be called from that submission
# path (every submission vs. only on explicit completion) is an open
# product decision the plan deliberately leaves to the product owner --
# see Phase 6 of docs/superpowers/plans/2026-07-02-lti-integration.md.
# Nothing here wires an automatic trigger; these are the primitives a
# follow-up change would call.


def record_ags_endpoint(user: User, platform: LtiPlatform, message_launch) -> None:
    """
    Persist this launch's AGS endpoint claim (if granted) onto the
    student's LtiUserLink. A no-op if this launch didn't grant grade-
    passback scope -- most launches for a student without a gradable
    assignment context won't.
    """
    if not message_launch.has_ags():
        return
    endpoint = message_launch.get_launch_data().get(
        "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
    )
    if not endpoint:
        return
    LtiUserLink.objects.filter(user=user, platform=platform).update(ags_endpoint=endpoint)


def _ags_service_for(user: User, platform: LtiPlatform) -> AssignmentsGradesService | None:
    """
    Reconstruct AGS access for (user, platform) from whatever endpoint was
    captured at their most recent gradable launch. Returns None if this
    student has never launched into a context that granted grade-passback
    scope on this platform yet.
    """
    link = (
        LtiUserLink.objects.filter(user=user, platform=platform)
        .exclude(ags_endpoint__isnull=True)
        .first()
    )
    if link is None:
        return None
    connector = ServiceConnector(build_registration(platform))
    return AssignmentsGradesService(connector, link.ags_endpoint)


def _platform_for_grade_passback(user: User) -> LtiPlatform | None:
    """
    Which institution should this student's grade go to? Requires exactly
    one platform with captured AGS access for this user -- if they're
    LTI-linked to more than one institution, publishing is skipped rather
    than guessing, since a misdirected grade is worse than a missing one.
    A student enrolled via multiple institutions is an edge case this
    phase doesn't try to solve.
    """
    platform_ids = (
        LtiUserLink.objects.filter(user=user)
        .exclude(ags_endpoint__isnull=True)
        .values_list("platform_id", flat=True)
        .distinct()
    )
    if len(platform_ids) != 1:
        return None
    return LtiPlatform.objects.get(pk=platform_ids[0])


def ensure_line_item(ags_service: AssignmentsGradesService, platform: LtiPlatform, pco) -> LtiLineItem:
    """
    Find or create the LtiLineItem mapping for this (pco, platform) pair,
    tagged by the PCO's own primary key so repeat calls -- from any
    student's AGS context on this platform -- resolve to the same
    platform-side line item rather than creating a duplicate gradebook
    column each time.
    """
    existing = LtiLineItem.objects.filter(pco=pco, platform=platform).first()
    if existing is not None:
        return existing

    new_line_item = LineItem()
    new_line_item.set_score_maximum(100)
    new_line_item.set_label(pco.playlist.name)
    new_line_item.set_tag(f"harmonylab-pco-{pco.pk}")

    found = ags_service.find_or_create_lineitem(new_line_item, "tag")
    return LtiLineItem.objects.create(pco=pco, platform=platform, line_item_id=found.get_id())


def publish_score(user: User, pco) -> bool:
    """
    Push this student's current progress on `pco` to their LMS gradebook,
    as a percentage (0-100 of scoreMaximum=100). Reuses the exact same
    progress_pct computation the student's own course page already shows
    (apps.student.unit_progress._playlist_stats) -- no separate scoring
    logic to keep in sync.

    Returns False (a no-op, not an error) if this student has no usable
    LTI grade-passback context yet -- e.g. they've never launched into a
    gradable assignment, or the institution didn't grant score-publish
    scope. Returns True if a grade was sent.
    """
    platform = _platform_for_grade_passback(user)
    if platform is None:
        return False

    ags_service = _ags_service_for(user, platform)
    if ags_service is None or not ags_service.can_put_grade():
        return False

    link = LtiUserLink.objects.get(user=user, platform=platform)
    line_item = ensure_line_item(ags_service, platform, pco)

    from apps.student.unit_progress import _batch_playlist_data, _playlist_stats

    raw = _batch_playlist_data(user, [pco.playlist])
    stats = _playlist_stats(pco.playlist, raw[pco.playlist.pk])
    progress_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0

    grade = Grade()
    grade.set_score_given(progress_pct)
    grade.set_score_maximum(100)
    grade.set_activity_progress("Completed" if progress_pct >= 100 else "InProgress")
    grade.set_grading_progress("FullyGraded")
    grade.set_user_id(link.sub)

    ags_service.put_grade(grade, LineItem({"id": line_item.line_item_id}))
    return True
