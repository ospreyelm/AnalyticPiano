import json
import re
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from apps.exercises.models import Playlist, Exercise, ExercisePlaylistOrdered
from apps.exercises.taxonomy_reader import TaxonomyReader

def _unit_new_chords(unit_num: int, family: str = "roman") -> set[str]:
    """Chords introduced at this unit, from taxonomy."""
    return TaxonomyReader.get_new_values(str(unit_num), family)


def _mode_to_family(mode: str) -> str:
    if mode in ("figures", "figures_unabbreviated", "play_figures"):
        return "figured_bass"
    return "roman"


def _mode_display_label(mode: str) -> str:
    if mode == "roman":
        return "Roman Numeral Analysis"
    return mode


def _build_playlist_name(unit_num, title: str, mode_label: str) -> str:
    """Playlist.name is max_length=64; truncate the title to fit."""
    name = f"Unit {unit_num} — {title} ({mode_label})"
    if len(name) <= 64:
        return name
    prefix = f"Unit {unit_num} — "
    suffix = f" ({mode_label})"
    max_title_len = max(0, 64 - len(prefix) - len(suffix))
    return f"{prefix}{title[:max_title_len].rstrip()}{suffix}"


# parents[4] from this file = repo root
TAXONOMY_PATH = Path(__file__).resolve().parents[4] / "music_theory_taxonomy_with_branches.json"

User = get_user_model()


def _lookup_unit(unit_num: int) -> dict | None:
    with open(TAXONOMY_PATH) as f:
        taxonomy = json.load(f)
    for branch in taxonomy:
        for tier in branch.get("tiers", []):
            for unit in tier.get("units", []):
                if str(unit["n"]) == str(unit_num):
                    return unit
    return None


def _parse_range(text: str) -> list[int]:
    text = text.strip()
    if "-" in text:
        start, end = text.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(text)]


def _raw_label(slice_dict: dict, family: str = "roman") -> str | None:
    content = slice_dict.get("content", {})
    if family == "figured_bass":
        raw = content.get("raw_figured_bass")
        if raw is not None:
            from apps.exercises.utils.figured_bass import abbreviate_figured_bass
            return abbreviate_figured_bass(raw)
        return None
    return content.get("roman_numeral") or content.get("raw_roman_numeral")


def _out_of_scope_ratio(ex, cumulative, family="roman"):
    analysis = ex.data.get("score", {}).get("umto", {}).get("analysis", [])
    if not analysis:
        return 0.0
    out = sum(1 for s in analysis if _raw_label(s, family) not in cumulative)
    return out / len(analysis)


def _new_value_event_count(ex, new_set, family="roman"):
    analysis = ex.data.get("score", {}).get("umto", {}).get("analysis", [])
    return sum(1 for s in analysis if _raw_label(s, family) in new_set)


def _targetable_event_ratio(ex, cumulative, family="roman"):
    analysis = ex.data.get("score", {}).get("umto", {}).get("analysis", [])
    if not analysis:
        return 0.0
    good = sum(1 for s in analysis if _raw_label(s, family) in cumulative)
    return good / len(analysis)


def _exercise_order_key(ex, unit_num: int, family: str = "roman"):
    cumulative = TaxonomyReader.get_cumulative_values(str(unit_num), family)
    new_set = TaxonomyReader.get_new_values(str(unit_num), family)
    return (
        _out_of_scope_ratio(ex, cumulative, family),
        -_new_value_event_count(ex, new_set, family),
        -_targetable_event_ratio(ex, cumulative, family),
        ex.complexity,
        Command._extract_riem_phrase(ex.description or ""),
    )


def _select_bach_candidates(*, author, unit_num: int, mode: str, riem_range: list[int], no_chord_filter: bool):
    unit_tag = f"unit:{unit_num}"
    mode_tag = f"mode:{mode}"
    riem_set = set(riem_range)
    candidates = Exercise.objects.filter(
        authored_by=author,
        skill_tags__contains=[unit_tag],
    ).filter(
        skill_tags__contains=[mode_tag],
    )

    # Quality exclusions:
    # 1. No key changes permitted before modulation is formally taught (units 19-20)
    if unit_num < 19:
        candidates = candidates.filter(skill_tags__contains=["no_key_change"])
    # 2. Avoid interior rests
    candidates = candidates.filter(skill_tags__contains=["no_interior_rests"])

    family = _mode_to_family(mode)
    require_new_chords = (
        not no_chord_filter
        and mode in ("roman", "figures", "play_figures", "matching")
    )
    selected = []
    for ex in candidates:
        riem_num, _ = Command._extract_riem_phrase(ex.description or "")
        if riem_num not in riem_set:
            continue
        if require_new_chords and not Command._has_new_chord(ex, unit_num, family):
            continue
        selected.append(ex)
    selected.sort(key=lambda ex: _exercise_order_key(ex, unit_num, family))
    return selected


class Command(BaseCommand):
    help = "Import Bach phrases for a unit and create an adaptive (non-dynamic) playlist with explicit exercise ordering."

    @staticmethod
    def _extract_riem_phrase(description: str) -> tuple[int, int]:
        # Expected shape: "Bach R22 - Phrase 3 (mm.11-15) [play]"
        m = re.search(r"R(\d+)\s*-\s*Phrase\s*(\d+)", description or "")
        if not m:
            return (0, 0)
        return (int(m.group(1)), int(m.group(2)))

    @staticmethod
    def _has_new_chord(ex: "Exercise", unit_num: int, family: str = "roman") -> bool:
        """Return True if exercise analysis contains at least one chord new to unit_num."""
        new_chords = _unit_new_chords(unit_num, family)
        if not new_chords:
            return True  # no new chords defined — don't filter
        analysis = ex.data.get("score", {}).get("umto", {}).get("analysis", [])
        labels = set()
        for s in analysis:
            label = _raw_label(s, family)
            if label:
                labels.add(label)
        return bool(labels & new_chords)

    def add_arguments(self, parser):
        parser.add_argument("--unit", type=int, required=True)
        parser.add_argument("--riemenschneider", type=str, required=True)
        parser.add_argument("--author", type=str, required=True)
        parser.add_argument("--mode", type=str,
                            choices=["roman", "play", "play_figures", "figures", "figures_unabbreviated", "matching"], default="roman")
        parser.add_argument("--min-measures", type=int, default=3)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-chord-filter", action="store_true",
                            help="Skip the new-chord requirement filter")
        parser.add_argument("--overwrite", action="store_true",
                            help="Overwrite existing exercises (re-import)")
        parser.add_argument("--playlist-only", action="store_true",
                            help="Skip import loop; only create/update playlist from already-imported exercises")

    def handle(self, *args, **options):
        unit_num = options["unit"]
        riem_range = _parse_range(str(options["riemenschneider"]))
        author_email = options["author"]
        mode = options["mode"]
        min_measures = options["min_measures"]
        make_public = options["public"]
        dry_run = options["dry_run"]

        unit_meta = _lookup_unit(unit_num)
        if unit_meta is None:
            raise CommandError(f"Unit {unit_num} not found in taxonomy.")
        title = unit_meta["title"]
        self.stdout.write(f"Unit {unit_num}: {title}")

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{author_email}'.")

        unit_tag = f"unit:{unit_num}"
        mode_tag = f"mode:{mode}"
        unit_skill_tags = list(unit_meta.get("tags", []))
        playlist_skill_tags = [unit_tag, mode_tag] + [
            tag for tag in unit_skill_tags if tag not in (unit_tag, mode_tag)
        ]
        playlist_only = options.get("playlist_only", False)
        if playlist_only:
            self.stdout.write("--playlist-only: skipping import, using existing exercises.")
        else:
            self.stdout.write(f"Importing Riemenschneider {riem_range[0]}\u2013{riem_range[-1]} ({len(riem_range)} chorales)...")
            for riem_num in riem_range:
                self.stdout.write(f"  R{riem_num}...")
                if not dry_run:
                    call_command("import_bach_phrases",
                                 riemenschneider=riem_num, author=author_email,
                                 mode=mode, min_measures=min_measures,
                                 extra_tags=[unit_tag, mode_tag], public=make_public,
                                 overwrite=options.get("overwrite", False))

        playlist_name = _build_playlist_name(unit_num, title, _mode_display_label(mode))
        if dry_run:
            self.stdout.write(f"[dry-run] Would create playlist: {playlist_name}")
            return

        # Scope by authored_by to prevent cross-teacher collision on same name
        playlist, created = Playlist.objects.get_or_create(
            name=playlist_name,
            authored_by=author,
            defaults=dict(is_dynamic=False, is_adaptive=True,
                          skill_tags=playlist_skill_tags, is_public=True),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = True
            if make_public:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in playlist_skill_tags:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.save()

        # Build static ordered exercise membership from imported corpus subset.
        # This preserves deterministic sequencing like the original Unit 9 flow.
        if not dry_run:
            selected = _select_bach_candidates(
                author=author,
                unit_num=unit_num,
                mode=mode,
                riem_range=riem_range,
                no_chord_filter=options.get("no_chord_filter", False),
            )

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for idx, ex in enumerate(selected, start=1):
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=idx,
                    is_adaptive_entry=(idx == 1),
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Linked {len(selected)} exercises to playlist '{playlist_name}' in static order."
                )
            )

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Playlist '{playlist_name}' ({playlist.id}) — {action}"))
