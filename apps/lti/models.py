from django.contrib.auth import get_user_model
from django.db import models
from django_better_admin_arrayfield.models.fields import ArrayField

User = get_user_model()


class LtiPlatform(models.Model):
    """
    One row per institution's LMS instance (e.g. one college's Moodle, one
    high school's Canvas). Multi-tenant by construction: a second
    institution is a new row here, not a code change.

    ``agreement_signed_at`` and ``is_active`` gate whether this platform can
    serve real course data. A platform can be registered and its launch flow
    tested (Phase 3) before the institution's data-sharing agreement is
    signed, but the launch view must refuse to serve a real course until
    both are set — see the spec's FERPA framing
    (docs/superpowers/specs/2026-07-02-student-dashboard-lti-design.md).
    """

    name = models.CharField(
        max_length=120,
        help_text="Display name, e.g. 'Example College Moodle'.",
    )
    issuer = models.CharField(max_length=255, unique=True)
    client_id = models.CharField(max_length=255)
    deployment_ids = ArrayField(
        models.CharField(max_length=255),
        default=list,
        blank=True,
        help_text="One platform can have multiple LTI deployment ids.",
    )
    auth_login_url = models.URLField(max_length=500)
    auth_token_url = models.URLField(max_length=500)
    jwks_url = models.URLField(max_length=500)

    agreement_signed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date the institution's data-sharing/FERPA agreement was "
        "signed. Null means this platform cannot serve real course data.",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Must be true, in addition to agreement_signed_at being "
        "set, before launches for this platform are served.",
    )

    class Meta:
        verbose_name = "LTI Platform"
        verbose_name_plural = "LTI Platforms"

    def __str__(self):
        return self.name

    @property
    def is_ready_for_real_courses(self) -> bool:
        return self.is_active and self.agreement_signed_at is not None


class LtiUserLink(models.Model):
    """
    Links a Django User to their identity on one LTI platform.

    Keyed on (platform, sub), not just sub: the same opaque sub value can
    legitimately be issued by two different institutions, so platform scoping
    is what keeps multiple institutions' students from colliding in this
    table.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lti_links")
    platform = models.ForeignKey(LtiPlatform, on_delete=models.CASCADE, related_name="user_links")
    sub = models.CharField(max_length=255)

    class Meta:
        verbose_name = "LTI User Link"
        verbose_name_plural = "LTI User Links"
        unique_together = ("platform", "sub")

    def __str__(self):
        return f"{self.platform.name} — {self.sub}"


class LtiLineItem(models.Model):
    """
    Maps a PlaylistCourseOrdered assignment row to the platform-side AGS
    line item used for grade passback. No new assignment model — this is an
    additive mapping onto the existing PCO row.
    """

    pco = models.ForeignKey(
        "exercises.PlaylistCourseOrdered",
        on_delete=models.CASCADE,
        related_name="lti_line_items",
    )
    platform = models.ForeignKey(LtiPlatform, on_delete=models.CASCADE, related_name="line_items")
    line_item_id = models.CharField(
        max_length=500,
        help_text="The platform-side line item resource id/URL.",
    )

    class Meta:
        verbose_name = "LTI Line Item"
        verbose_name_plural = "LTI Line Items"
        unique_together = ("pco", "platform")

    def __str__(self):
        return f"{self.pco} → {self.platform.name}"
