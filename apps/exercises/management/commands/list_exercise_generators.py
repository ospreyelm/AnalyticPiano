"""Print the catalog of exercise-generation and exercise-refresh management
commands grouped by exercise type. Use as a quick reference when admin
work spans multiple exercise types.

Usage:
    python manage.py list_exercise_generators
"""
from django.core.management.base import BaseCommand


# Each entry: (group label, [(command, summary, example)]).
CATALOG = [
    ("Bach chorale phrases (Riemenschneider)", [
        (
            "import_bach_phrases",
            "Import a single Riemenschneider phrase as identification/playback/match/figures/harmonization-source exercises.",
            "python manage.py import_bach_phrases --riemenschneider 3 --author admin@example.com --mode roman --extra-tags unit:9",
        ),
        (
            "generate_harmonization",
            "Derive a harmonization variant from an existing UMTO source (locks bass; builds targets).",
            "python manage.py generate_harmonization --source EB16DF --author admin@example.com --locked-voices B --prompt figured_bass",
        ),
        (
            "render_harmonization_review",
            "Render a visual review page for a harmonization exercise.",
            "python manage.py render_harmonization_review --source EB57LQ",
        ),
    ]),
    ("Pitch identification (Unit 1)", [
        (
            "generate_unit1",
            "Generate the Unit 1 pitch-identification curriculum.",
            "python manage.py generate_unit1 --author admin@example.com",
        ),
        (
            "duplicate_chorale_as_identification",
            "Spin a chorale into single-voice pitch-identification variants.",
            "python manage.py duplicate_chorale_as_identification --source EB16DF --voices soprano alto",
        ),
    ]),
    ("Rhythm and meter (Unit 2)", [
        (
            "generate_unit2_meter_exercises",
            "Generate Unit 2 meter-identification exercises.",
            "python manage.py generate_unit2_meter_exercises --author admin@example.com",
        ),
        (
            "generate_unit2_meter_reference",
            "Generate Unit 2 meter reference exercises (display-only).",
            "python manage.py generate_unit2_meter_reference --author admin@example.com",
        ),
        (
            "generate_unit2_barline_exercises",
            "Generate Unit 2 barline-placement exercises.",
            "python manage.py generate_unit2_barline_exercises --author admin@example.com",
        ),
    ]),
    ("Scales and key signatures (Unit 3)", [
        (
            "generate_unit3_key_sig_exercises",
            "Generate Unit 3 key-signature identification exercises.",
            "python manage.py generate_unit3_key_sig_exercises --author admin@example.com",
        ),
        (
            "generate_unit3_scale_exercises",
            "Generate Unit 3 scale-construction exercises.",
            "python manage.py generate_unit3_scale_exercises --author admin@example.com",
        ),
    ]),
    ("Playlists and curriculum wiring", [
        (
            "create_unit_playlist",
            "Create a per-unit Playlist that bundles existing exercises by skill tag.",
            "python manage.py create_unit_playlist --unit 9",
        ),
        (
            "create_smart_playlist",
            "Create an adaptive (smart) playlist seeded from skill-tag filters.",
            "python manage.py create_smart_playlist --name 'My adaptive set' --tags I V V7",
        ),
        (
            "rebuild_unit1_playlists",
            "Rebuild Unit 1 playlists from current taxonomy.",
            "python manage.py rebuild_unit1_playlists",
        ),
        (
            "fix_unit3_playlists",
            "Repair Unit 3 playlist memberships (one-off cleanup).",
            "python manage.py fix_unit3_playlists",
        ),
    ]),
    ("Refresh / recompute (do NOT regenerate exercise rows)", [
        (
            "refresh_all_exercises",
            "Dispatcher: refresh analysis + targets across all UMTO exercises in DB. Safe to run after analysis-pipeline fixes.",
            "python manage.py refresh_all_exercises --dry-run",
        ),
        (
            "recompute_chorale_analysis",
            "Rebuild score.umto.analysis on chorale-derived rows (tagged riem:N) without re-importing music21.",
            "python manage.py recompute_chorale_analysis --tag qa:harm_fb_audit_2026_05_18_declared_key",
        ),
        (
            "recompute_harmonization_targets",
            "Rebuild harmonizationTargets on harmonization rows from their stored score.umto.analysis.",
            "python manage.py recompute_harmonization_targets --tag qa:harm_fb_audit_2026_05_18_declared_key",
        ),
        (
            "backfill_skill_tags",
            "Re-run skills_analyzer over all UMTO rows and write skill_tags + complexity.",
            "python manage.py backfill_skill_tags --all",
        ),
        (
            "backfill_raw_roman_numeral",
            "Backfill raw_roman_numeral on existing analysis slices.",
            "python manage.py backfill_raw_roman_numeral",
        ),
        (
            "reanalyze_knowledge_graph",
            "Recompute knowledge-graph edges from current exercise tags.",
            "python manage.py reanalyze_knowledge_graph",
        ),
    ]),
]


class Command(BaseCommand):
    help = "Print the catalog of exercise-generation and refresh management commands."

    def handle(self, *args, **options):
        for group, entries in CATALOG:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{group}"))
            for cmd, summary, example in entries:
                self.stdout.write(self.style.SUCCESS(f"  {cmd}"))
                self.stdout.write(f"    {summary}")
                self.stdout.write(self.style.HTTP_INFO(f"    $ {example}"))
        self.stdout.write("")
