"""
Tool-side LTI configuration: adapts LtiPlatform DB rows into pylti1p3's
registration/deployment interface, plus the readiness gate that decides
whether a launch may proceed past the "waiting on institutional sign-off"
page.

Identity resolution (Phase 4) and grade passback (Phase 6) of
docs/superpowers/plans/2026-07-02-lti-integration.md are not implemented
here yet.
"""
from __future__ import annotations

import functools

from django.conf import settings
from pylti1p3.deployment import Deployment
from pylti1p3.exception import LtiException
from pylti1p3.registration import Registration
from pylti1p3.tool_config import ToolConfAbstract

from apps.lti.models import LtiPlatform


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


class ToolConfig(ToolConfAbstract):
    """
    Adapts LtiPlatform rows into pylti1p3's Registration/Deployment
    interface. One row per institution (see LtiPlatform docstring) --
    onboarding a second college or a high school is a new row, not a code
    change here.
    """

    def _build_registration(self, platform: LtiPlatform) -> Registration:
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

    def find_registration_by_issuer(self, iss, *args, **kwargs) -> Registration:
        platform = LtiPlatform.objects.filter(issuer=iss).first()
        if platform is None:
            raise LtiException(f"Unknown issuer: {iss}")
        return self._build_registration(platform)

    def find_registration_by_params(self, iss, client_id, *args, **kwargs) -> Registration:
        platform = LtiPlatform.objects.filter(issuer=iss, client_id=client_id).first()
        if platform is None:
            raise LtiException(f"Unknown issuer/client_id: {iss} / {client_id}")
        return self._build_registration(platform)

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
