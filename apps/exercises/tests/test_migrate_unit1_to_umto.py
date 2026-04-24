from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
import os

from apps.exercises.models import Exercise


class MigrateUnit1ToUMTOTests(TestCase):
    def test_migrate_unit1_to_umto_converts_legacy_row(self):
        # Use environment variable to bypass legacy block (for future Task 15)
        os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"] = "1"

        # Cleanup any leftover from previous failed runs
        test_email = "migrate_test_author@example.com"
        get_user_model().objects.filter(email=test_email).delete()
        Exercise.objects.filter(description="migration_test_legacy").delete()

        author = get_user_model().objects.create_user(email=test_email, password="pw")
        legacy_data = {
            "type": "chorale_identification",
            "introText": "Legacy",
            "score": {
                "meta": {"key": "C", "time": "4/4"},
                "measures": [{
                    "staves": {"treble": {"voices": [{"items": [
                        {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                    ]}]}}
                }]
            }
        }
        ex = Exercise.objects.create(
            description="migration_test_legacy",
            data=legacy_data,
            authored_by=author,
            skill_tags=["unit:1"],
        )

        call_command("migrate_unit1_to_umto")

        ex.refresh_from_db()
        self.assertTrue(ex.data["isUMTO"])
        self.assertEqual(ex.data["score"]["umto"]["voices"]["S"][0]["pitch"]["midi"], 60)
