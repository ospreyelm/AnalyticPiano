"""
apps/lti/tests/test_views.py

End-to-end OIDC login + launch flow tests, driven entirely against a fake
LtiPlatform and a locally generated "platform" keypair -- no real Moodle
or Canvas needed (see docs/superpowers/plans/2026-07-02-lti-integration.md
Phase 3's testability note). Exercises the readiness gate from
docs/superpowers/specs/2026-07-02-student-dashboard-lti-design.md: an
unsigned/inactive platform gets the friendly "waiting on institutional
sign-off" page; a ready platform reaches Phase 4's identity resolution.
"""
from __future__ import annotations

import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import authenticate
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from pylti1p3.registration import Registration

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER
from apps.lti.models import LtiPlatform, LtiUserLink


def _generate_keypair() -> tuple[str, str]:
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


class LtiLaunchFlowTestCase(TestCase):
    """Base: builds a fake platform and drives the real login -> launch
    flow through the actual views, the way a browser redirected from an
    LMS would."""

    def setUp(self):
        self.platform_private_key, self.platform_public_key = _generate_keypair()
        self.jwk = Registration.get_jwk(self.platform_public_key)
        self.kid = self.jwk["kid"]

        self.platform = LtiPlatform.objects.create(
            name="Test Moodle",
            issuer="https://moodle.example.edu",
            client_id="test-client-id",
            deployment_ids=["deployment-1"],
            auth_login_url="https://moodle.example.edu/mod/lti/auth.php",
            auth_token_url="https://moodle.example.edu/mod/lti/token.php",
            jwks_url="https://moodle.example.edu/mod/lti/certs.php",
        )
        self.client = Client()

    def _do_login(self) -> tuple[str, str]:
        """Drives the real /lti/login/ view; returns (state, nonce) parsed
        from the redirect it issues back toward the platform's auth URL."""
        response = self.client.get(
            reverse("lti:login"),
            {
                "iss": self.platform.issuer,
                "login_hint": "test-login-hint",
                "client_id": self.platform.client_id,
                "target_link_uri": "http://testserver/lti/launch/",
            },
        )
        self.assertEqual(response.status_code, 302)
        params = {k: v[0] for k, v in parse_qs(urlparse(response["Location"]).query).items()}
        return params["state"], params["nonce"]

    def _build_id_token(self, nonce: str, **claim_overrides) -> str:
        now = int(time.time())
        payload = {
            "iss": self.platform.issuer,
            "aud": self.platform.client_id,
            "sub": "test-student-sub",
            "exp": now + 300,
            "iat": now,
            "nonce": nonce,
            "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "deployment-1",
            "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
            "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "resource-1"},
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
            ],
        }
        payload.update(claim_overrides)
        return pyjwt.encode(
            payload,
            self.platform_private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )

    def _do_launch(self, state: str, id_token: str):
        # The real flow fetches the platform's JWKS over HTTP; stub that
        # one network call with the fake platform's own public key.
        with patch(
            "pylti1p3.message_launch.MessageLaunch.fetch_public_key",
            return_value={"keys": [self.jwk]},
        ):
            return self.client.post(
                reverse("lti:launch"),
                {"id_token": id_token, "state": state},
            )


class LaunchReadinessGateTest(LtiLaunchFlowTestCase):
    def test_not_ready_platform_shows_friendly_page(self):
        state, nonce = self._do_login()
        response = self._do_launch(state, self._build_id_token(nonce))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Waiting on institutional approval")
        self.assertContains(response, "Test Moodle")

    def test_ready_platform_passes_the_gate(self):
        self.platform.is_active = True
        self.platform.agreement_signed_at = timezone.now()
        self.platform.save()

        state, nonce = self._do_login()
        response = self._do_launch(state, self._build_id_token(nonce))
        self.assertRedirects(response, reverse("student:home"), fetch_redirect_response=False)
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_unknown_deployment_id_is_rejected(self):
        state, nonce = self._do_login()
        id_token = self._build_id_token(
            nonce,
            **{
                "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "not-a-real-deployment",
            },
        )
        response = self._do_launch(state, id_token)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Couldn't verify this connection", status_code=400)

    def test_bad_signature_is_rejected(self):
        state, nonce = self._do_login()
        other_private_key, _ = _generate_keypair()
        id_token = pyjwt.encode(
            {
                "iss": self.platform.issuer,
                "aud": self.platform.client_id,
                "sub": "test-student-sub",
                "exp": int(time.time()) + 300,
                "iat": int(time.time()),
                "nonce": nonce,
                "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
                "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "deployment-1",
                "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
                "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "resource-1"},
                "https://purl.imsglobal.org/spec/lti/claim/roles": [
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
                ],
            },
            other_private_key,  # wrong key -- not the one whose JWKS we stubbed
            algorithm="RS256",
            headers={"kid": self.kid},
        )
        response = self._do_launch(state, id_token)
        self.assertEqual(response.status_code, 400)


class IdentityResolutionTest(LtiLaunchFlowTestCase):
    """Phase 4: sub-only identity resolution -- must work with no name/email
    claims present (an institution's anonymous LTI configuration), never
    require them."""

    def setUp(self):
        super().setUp()
        self.platform.is_active = True
        self.platform.agreement_signed_at = timezone.now()
        self.platform.save()

    def test_anonymous_launch_creates_unusable_password_user(self):
        state, nonce = self._do_login()
        self._do_launch(state, self._build_id_token(nonce))

        link = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub")
        user = link.user
        self.assertTrue(user.email.endswith("@lti.harmonylab.invalid"))
        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")
        self.assertEqual(user.role, ROLE_STUDENT)
        self.assertFalse(user.has_usable_password())

    def test_launch_with_released_name_and_email_stores_them(self):
        state, nonce = self._do_login()
        id_token = self._build_id_token(
            nonce,
            email="student@example.edu",
            given_name="Ana",
            family_name="Garcia",
        )
        self._do_launch(state, id_token)

        link = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub")
        user = link.user
        self.assertEqual(user.email, "student@example.edu")
        self.assertEqual(user.first_name, "Ana")
        self.assertEqual(user.last_name, "Garcia")
        self.assertFalse(user.has_usable_password())

    def test_repeat_launch_reuses_same_user(self):
        state, nonce = self._do_login()
        self._do_launch(state, self._build_id_token(nonce))
        first_user_id = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub").user_id

        state, nonce = self._do_login()
        self._do_launch(state, self._build_id_token(nonce))

        self.assertEqual(LtiUserLink.objects.filter(platform=self.platform, sub="test-student-sub").count(), 1)
        second_user_id = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub").user_id
        self.assertEqual(first_user_id, second_user_id)

    def test_teacher_role_redirects_to_teacher_landing(self):
        state, nonce = self._do_login()
        id_token = self._build_id_token(
            nonce,
            **{
                "https://purl.imsglobal.org/spec/lti/claim/roles": [
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"
                ],
            },
        )
        response = self._do_launch(state, id_token)
        self.assertRedirects(response, reverse("teacher:course-list"), fetch_redirect_response=False)

        link = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub")
        self.assertEqual(link.user.role, ROLE_TEACHER)

    def test_lti_provisioned_account_cannot_be_authenticated_directly(self):
        """An LTI-provisioned account must never be reachable through the
        normal email/password login path -- only through a fresh, valid
        launch tied to its (platform, sub)."""
        state, nonce = self._do_login()
        self._do_launch(state, self._build_id_token(nonce))
        user = LtiUserLink.objects.get(platform=self.platform, sub="test-student-sub").user

        self.assertFalse(user.check_password("anything"))
        self.assertIsNone(authenticate(username=user.email, password="anything"))
        self.assertIsNone(authenticate(username=user.email, password=""))


class JwksViewTest(TestCase):
    def test_jwks_returns_a_key(self):
        response = self.client.get(reverse("lti:jwks"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["keys"]), 1)
        self.assertIn("kid", data["keys"][0])
