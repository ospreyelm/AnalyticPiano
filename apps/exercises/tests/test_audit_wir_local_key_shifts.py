from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.tests.umto_test_helpers import make_umto_exercise


def _create_user(email: str):
    return get_user_model().objects.create_user(
        email=email,
        password="test-password",
    )


class AuditWiRLocalKeyShiftsTests(TestCase):
    def test_reports_inferred_shift_by_riemenschneider_number(self):
        author = _create_user("wir-audit@example.test")
        make_umto_exercise(
            author,
            description="BWV R17 audit fixture",
            skill_tags=["riem:17", "unit:11"],
        )
        make_umto_exercise(
            author,
            description="BWV R1 audit fixture",
            skill_tags=["riem:1", "unit:11"],
        )

        out = StringIO()
        call_command("audit_wir_local_key_shifts", stdout=out)

        lines = out.getvalue().splitlines()
        self.assertIn("R1 0 rows=1", lines)
        self.assertIn("R17 +2 rows=1", lines)

    def test_recompute_chorale_analysis_reports_inferred_shift(self):
        author = _create_user("wir-refresh-audit@example.test")
        make_umto_exercise(
            author,
            description="BWV R17, mm.1-6 refresh fixture",
            skill_tags=["riem:17", "unit:11"],
        )

        out = StringIO()
        call_command("recompute_chorale_analysis", riem=17, dry_run=True, stdout=out)

        self.assertIn("local-key shift +2", out.getvalue())
