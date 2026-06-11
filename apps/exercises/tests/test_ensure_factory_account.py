"""Tests for ensure_factory_account management command."""
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from apps.accounts.models import User, ROLE_TEACHER


class EnsureFactoryAccountTestCase(TestCase):
    """Test the ensure_factory_account command."""

    def test_create_factory_account_idempotent(self):
        """Calling the command twice yields exactly one user with that email."""
        email = "factory@monteverdi.app"

        # First call - should create
        out = StringIO()
        call_command("ensure_factory_account", stdout=out)
        output1 = out.getvalue()
        self.assertIn("Created factory account", output1)
        self.assertIn(email, output1)

        # Verify the user was created
        user = User.objects.get(email=email)
        user_id = user.id

        # Second call - should find existing
        out = StringIO()
        call_command("ensure_factory_account", stdout=out)
        output2 = out.getvalue()
        self.assertIn("Factory account exists", output2)
        self.assertIn(email, output2)

        # Verify exactly one user with this email
        users_count = User.objects.filter(email=email).count()
        self.assertEqual(users_count, 1)

        # Verify the same user ID
        user_again = User.objects.get(email=email)
        self.assertEqual(user_again.id, user_id)

    def test_factory_account_role_is_teacher(self):
        """The factory account should have teacher role."""
        email = "factory@monteverdi.app"
        call_command("ensure_factory_account")

        user = User.objects.get(email=email)
        self.assertEqual(user.role, ROLE_TEACHER)

    def test_factory_account_password_unusable(self):
        """The factory account should not have a usable password."""
        email = "factory@monteverdi.app"
        call_command("ensure_factory_account")

        user = User.objects.get(email=email)
        self.assertFalse(user.has_usable_password())

    def test_factory_account_custom_email(self):
        """The command should respect a custom email override."""
        custom_email = "custom-factory@example.com"
        out = StringIO()
        call_command("ensure_factory_account", email=custom_email, stdout=out)
        output = out.getvalue()

        self.assertIn("Created factory account", output)
        self.assertIn(custom_email, output)

        user = User.objects.get(email=custom_email)
        self.assertEqual(user.role, ROLE_TEACHER)
        self.assertFalse(user.has_usable_password())
