"""Dump an exercise's key decision fields (and optionally full data) by E-ID.

Lets an agent read the real shape of an exercise instead of guessing field
names through the browser. Run with the local settings that point at the dev DB:

    python manage.py dump_exercise EB61KJ --settings=harmony.settings.local
    python manage.py dump_exercise EB61KJ --full --settings=harmony.settings.local
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise


# Fields that decide grader selection / input UI / gating.
SUMMARY_KEYS = [
    "type",
    "mode",
    "analysisType",
    "inputMode",
    "inputModeFixed",
    "identMode",
    "exerciseId",
    "complexity_score",
    "allowed_answers",
    "isUMTO",
]


class Command(BaseCommand):
    help = "Dump an exercise's decision fields (type/mode/inputMode/analysisType) by E-ID."

    def add_arguments(self, parser):
        parser.add_argument("exercise_id", help="E-ID, e.g. EB61KJ")
        parser.add_argument(
            "--full",
            action="store_true",
            help="Print the full data JSON, not just the summary.",
        )

    def handle(self, *args, **options):
        eid = options["exercise_id"]
        ex = Exercise.objects.filter(id=eid).first()
        if ex is None:
            raise CommandError("No Exercise with id=%r" % eid)

        data = ex.data or {}
        meta = (
            (data.get("score") or {}).get("umto", {}).get("metadata", {})
            if isinstance(data.get("score"), dict)
            else {}
        )

        self.stdout.write("Exercise %s" % eid)
        self.stdout.write("-" * 40)
        for key in SUMMARY_KEYS:
            self.stdout.write("%-18s %r" % (key, data.get(key)))
        self.stdout.write("%-18s %r" % ("umto.metadata.mode", meta.get("mode")))
        self.stdout.write("%-18s %r" % ("umto.metadata.input_mode", meta.get("input_mode")))

        # Mirror the JS canonical discriminator (input_method_logic.resolveInputMethod).
        self.stdout.write("%-18s %r" % ("=> input_method", self._input_method(data, meta)))

        if options["full"]:
            self.stdout.write("-" * 40)
            self.stdout.write(json.dumps(data, indent=2, default=str))

    @staticmethod
    def _input_method(data, meta):
        im = data.get("inputModeFixed") or data.get("inputMode") or meta.get("input_mode")
        if im == "dropdown":
            return "dropdown"
        if im == "text":
            return "text"
        mode = data.get("mode") or meta.get("mode")
        if mode in ("identification", "chorale_identification", "analysis_match", "analysis"):
            return "dropdown"
        ex_type = data.get("type")
        if ex_type in ("identification", "chorale_identification"):
            return "dropdown"
        return "note_entry"
