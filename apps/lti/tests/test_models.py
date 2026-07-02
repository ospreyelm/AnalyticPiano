"""
apps/lti/tests/test_models.py

Model-level tests for the LTI app: multi-tenant uniqueness constraints and
the agreement-gate property that decides whether a platform may serve real
course data (docs/superpowers/specs/2026-07-02-student-dashboard-lti-design.md).
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.lti.models import LtiPlatform, LtiUserLink

User = get_user_model()


def _make_platform(n: int, **overrides) -> LtiPlatform:
    defaults = dict(
        name=f"Test Platform {n}",
        issuer=f"https://moodle-{n}.example.edu",
        client_id=f"client-{n}",
        deployment_ids=[f"deployment-{n}"],
        auth_login_url=f"https://moodle-{n}.example.edu/mod/lti/auth.php",
        auth_token_url=f"https://moodle-{n}.example.edu/mod/lti/token.php",
        jwks_url=f"https://moodle-{n}.example.edu/mod/lti/certs.php",
    )
    defaults.update(overrides)
    return LtiPlatform.objects.create(**defaults)


class LtiPlatformReadinessTest(TestCase):
    def test_not_ready_when_agreement_unsigned(self):
        platform = _make_platform(1, is_active=True, agreement_signed_at=None)
        self.assertFalse(platform.is_ready_for_real_courses)

    def test_not_ready_when_inactive_even_if_signed(self):
        platform = _make_platform(2, is_active=False, agreement_signed_at=timezone.now())
        self.assertFalse(platform.is_ready_for_real_courses)

    def test_ready_when_both_active_and_signed(self):
        platform = _make_platform(3, is_active=True, agreement_signed_at=timezone.now())
        self.assertTrue(platform.is_ready_for_real_courses)

    def test_deployment_ids_accepts_multiple(self):
        platform = _make_platform(4, deployment_ids=["dep-a", "dep-b", "dep-c"])
        platform.refresh_from_db()
        self.assertEqual(platform.deployment_ids, ["dep-a", "dep-b", "dep-c"])


class LtiUserLinkUniquenessTest(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(id=101, email="a@test.com", password="x")
        self.user_b = User.objects.create_user(id=102, email="b@test.com", password="x")
        self.platform_1 = _make_platform(11)
        self.platform_2 = _make_platform(12)

    def test_same_sub_across_two_platforms_does_not_collide(self):
        """The same opaque sub value from two different institutions must
        not be treated as the same identity — this is the whole point of
        keying on (platform, sub) rather than sub alone."""
        LtiUserLink.objects.create(user=self.user_a, platform=self.platform_1, sub="12345")
        link = LtiUserLink.objects.create(user=self.user_b, platform=self.platform_2, sub="12345")
        self.assertEqual(link.sub, "12345")
        self.assertEqual(LtiUserLink.objects.filter(sub="12345").count(), 2)

    def test_duplicate_platform_sub_pair_rejected(self):
        LtiUserLink.objects.create(user=self.user_a, platform=self.platform_1, sub="12345")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LtiUserLink.objects.create(user=self.user_b, platform=self.platform_1, sub="12345")
