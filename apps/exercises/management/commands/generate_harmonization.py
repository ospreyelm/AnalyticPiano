from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.harmonization.targets import build_targets_from_umto
from apps.exercises.harmonization.voice_completion_eligibility import (
    VoiceCompletionEligibilityError,
    validate_voice_completion_eligibility,
)
from apps.exercises.models import Exercise


def _harmonization_instruction(source_text: str | None) -> str:
    text = (source_text or "this phrase").strip()
    old_prefix = "Provide the Figured Bass for "
    if text.startswith(old_prefix):
        text = text[len(old_prefix):]
    return f"Realize the Figured Bass of {text}"


class Command(BaseCommand):
    help = "Generate a harmonization exercise from an existing UMTO source exercise."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Source Exercise id.")
        parser.add_argument("--author", required=True, help="Author email.")
        parser.add_argument("--locked-voices", dest="locked_voices", default="B")
        parser.add_argument(
            "--input-style",
            dest="input_style",
            default=None,
            choices=["per_voice"],
            help=(
                "Set to 'per_voice' to generate the SATB per-voice-completion "
                "variant (bass always locked, exactly one upper voice missing). "
                "Omit for the existing chord-entry harmonization exercise."
            ),
        )
        parser.add_argument("--prompt", default="figured_bass", choices=["figured_bass", "roman"])
        parser.add_argument("--voice-count", dest="voice_count", type=int, default=None)
        parser.add_argument("--min-voices", dest="min_voices", type=int, default=3)
        parser.add_argument("--max-voices", dest="max_voices", type=int, default=4)
        parser.add_argument("--max-displacement", dest="max_displacement", type=int, default=4)
        parser.add_argument("--public", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()

        try:
            source = Exercise.objects.get(id=options["source"])
        except Exercise.DoesNotExist as exc:
            raise CommandError(f"Source exercise not found: {options['source']}") from exc

        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Author not found: {options['author']}") from exc

        source_umto = source.data.get("score", {}).get("umto")
        if not source.data.get("isUMTO") or not source_umto:
            raise CommandError("Source exercise must be UMTO with score.umto")

        locked_voices = [v.strip() for v in options["locked_voices"].split(",") if v.strip()]
        voice_count_policy = {
            "expected": options["voice_count"],
            "min": options["min_voices"],
            "max": options["max_voices"],
        }

        umto = copy.deepcopy(source_umto)
        umto["metadata"]["mode"] = "harmonization"
        umto["metadata"]["locked_voices"] = locked_voices
        umto["metadata"]["voice_count_policy"] = voice_count_policy
        umto["metadata"]["harmonization_target_policy"] = {
            "source": "analysis_slice",
            "written_spelling_required": False,
            "midi_uses_pitch_class": True,
        }
        umto["metadata"]["max_voice_displacement"] = options["max_displacement"]
        umto["metadata"]["chord_settle_ms"] = 150
        umto["metadata"]["release_grace_ms"] = 120
        instruction = _harmonization_instruction(umto["metadata"].get("source"))
        umto["metadata"]["source"] = instruction

        input_style = options["input_style"]
        if input_style == "per_voice":
            try:
                validate_voice_completion_eligibility(umto)
            except VoiceCompletionEligibilityError as exc:
                raise CommandError(str(exc)) from exc
            umto["metadata"]["input_style"] = input_style

        targets = build_targets_from_umto(umto)
        if not targets:
            raise CommandError(
                f"Source exercise {source.id} produced zero targets — "
                "ensure score.umto.analysis is non-empty and bass voice events are present."
            )

        locked_str = ",".join(locked_voices)
        desc = f"Harm/{source.id}/L={locked_str}/v{options['min_voices']}-{options['max_voices']}"
        desc = desc[:60]
        existing = Exercise.objects.filter(description=desc, authored_by=author).first()
        if existing:
            self.stdout.write(f"Exists: {existing.id}")
            return

        data = copy.deepcopy(source.data)
        data["mode"] = "harmonization"
        data["analysisType"] = options["prompt"]
        data["score"]["umto"] = umto
        data["harmonizationTargets"] = targets
        data["introText"] = instruction

        skill_tags = list(source.skill_tags or []) + ["mode:harmonization"]
        if input_style:
            skill_tags.append(f"input_style:{input_style}")

        ex = Exercise.objects.create(
            description=desc,
            authored_by=author,
            data=data,
            is_public=options["public"],
            skill_tags=skill_tags,
            complexity=source.complexity,
        )
        ex.data["exerciseId"] = ex.id
        ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
        ex.save(update_fields=["data"])
        self.stdout.write(self.style.SUCCESS(f"Created {ex.id}"))
