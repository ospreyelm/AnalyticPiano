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
            "import_musicxml",
            "Import MusicXML through the UMTO representation router: stable multipart scores stay voices-kind; chordal/monophonic sources become chordal UMTO.",
            "python manage.py import_musicxml path/to/score.musicxml --author admin@example.com --public",
        ),
        (
            "import_legacy_chord_csv",
            "Import legacy CSV data.chord rows as chordal UMTO exercises. Use --dry-run first.",
            "python manage.py import_legacy_chord_csv exercises_2026-04-03.csv --author admin@example.com --dry-run --limit 10",
        ),
        (
            "import_bach_phrases",
            "Import single, range, or list of Riemenschneider phrases as identification/playback/match/figures/harmonization-source exercises.",
            "python manage.py import_bach_phrases --riemenschneider 1-10 --author admin@example.com --mode roman --extra-tags unit:9",
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
        (
            "generate_bach_unit_matrix",
            "Import Bach Riemenschneider phrases once per mode, then project them into per-unit playlists.",
            "python manage.py generate_bach_unit_matrix --riemenschneider 1-30 --units 9,10,11,12,14,16,17,18,19,20 --modes roman,figures,play,play_figures --author admin@example.com --public",
        ),
        (
            "deduplicate_bach_phrases",
            "Audit or delete unreferenced duplicate Bach phrase rows after switching to import-once generation.",
            "python manage.py deduplicate_bach_phrases --author admin@example.com",
        ),
        (
            "prune_non_satb_bach_phrases",
            "Dry-run or delete Bach phrase rows imported from non-four-part Riemenschneider sources.",
            "python manage.py prune_non_satb_bach_phrases --author admin@example.com --list",
        ),
        (
            "repair_bach_slice_barlines",
            "Dry-run or repair Bach phrase rows whose stored rendered measures drifted from source slice barlines.",
            "python manage.py repair_bach_slice_barlines --author admin@example.com --list",
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
    ("Intervals (Unit 4)", [
        (
            "generate_unit4",
            "Generate Unit 4 staged synthetic interval worksheet exercises.",
            "python manage.py generate_unit4 --author admin@example.com --public",
        ),
    ]),
    ("Triads and seventh chords (Unit 5)", [
        (
            "generate_unit5",
            "Generate Unit 5 chord-quality identification exercises (triads and/or seventh chords, staged choice counts).",
            "python manage.py generate_unit5 --type both --author admin@example.com --public",
        ),
    ]),
    ("Galant Compendium (Roman numerals)", [
        (
            "audit_compendium_cadences",
            "Export a no-DB CSV for reviewing Galant-compendium Roman numeral labels before import.",
            "python manage.py audit_compendium_cadences --out scratch/compendium_rn_review.csv",
        ),
        (
            "verify_compendium_realization",
            "Verify that the copied Z7 realization layer reproduces the checked-in compendium note JSON exactly.",
            "python manage.py verify_compendium_realization",
        ),
        (
            "import_compendium_cadences",
            "Import Roman-numeral identification exercises from the Galant compendium. Transposes templated cadences to multiple keys; groups into per-unit playlists. Use --preview for a dry run (no DB writes).",
            "python manage.py import_compendium_cadences --author admin@example.com --public --overwrite",
        ),
    ]),
    ("Branch B (Clausulae)", [
        (
            "generate_clausulae_b1",
            "Generate Branch B Units B1–B2: formal clausulae and simple 2-voice cadences.",
            "python manage.py generate_clausulae_b1 --author admin@example.com --public",
        ),
        (
            "generate_roman_from_clausulae",
            "Generate Roman numeral identification exercises from standard Clausulae cadences.",
            "python manage.py generate_roman_from_clausulae --unit 10 --author admin@example.com --voices 3 --public --overwrite",
        ),
        (
            "generate_harmonization_from_clausulae",
            "Generate figured-bass harmonization exercises from standard Clausulae cadences.",
            "python manage.py generate_harmonization_from_clausulae --unit 10 --author admin@example.com --voices 3 --public --overwrite",
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
            "audit_wir_local_key_shifts",
            "Report inferred WiR local-key transpositions by Riemenschneider number for existing Bach rows.",
            "python manage.py audit_wir_local_key_shifts --tag unit:11",
        ),
        (
            "recompute_chorale_analysis",
            "Rebuild score.umto.analysis on chorale-derived rows (tagged riem:N), including WiR local-key transposition, without re-importing rows.",
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
            "backfill_analysis_layer",
            "Backfill set_class/interval analytics into existing UMTO chordal analysis slices.",
            "python manage.py backfill_analysis_layer --dry-run",
        ),
        (
            "reanalyze_knowledge_graph",
            "Recompute knowledge-graph edges from current exercise tags.",
            "python manage.py reanalyze_knowledge_graph",
        ),
    ]),
    ("Theory verification", [
        (
            "dump_theory_goldens",
            "Emit candidate theory golden files (theory_golden/*.json) for expert review; merges by id and preserves review stamps.",
            "python manage.py dump_theory_goldens --dry-run",
        ),
        (
            "audit_figure_realization_coverage",
            "Report figured-bass figures in the corpus that don't map to a realization prototype (fall back to all-required).",
            "python manage.py audit_figure_realization_coverage --limit 20",
        ),
    ]),
    ("Simulation / QA", [
        (
            "simulate_adaptive_playlists",
            "Run a multi-student adaptive playlist simulation (3 students × 5 steps) and assert diversity, no-duplicates, and adaptivity properties. Writes playlist_simulation_report.json.",
            "python manage.py simulate_adaptive_playlists --output /tmp/report.json",
        ),
    ]),
    ("Factory library / infrastructure", [
        (
            "ensure_factory_account",
            "Idempotently create the factory system account (settings.FACTORY_USER_EMAIL) that owns official curated content.",
            "python manage.py ensure_factory_account",
        ),
        (
            "generate_factory_library",
            "Run the full factory-manifest seed (generators + curated playlists) under the factory account. --report/--verify are read-only.",
            "python manage.py generate_factory_library --units 1,2,9-20 --dry-run",
        ),
        (
            "export_factory_curated",
            "Dump hand-authored factory exercises + playlist memberships to data/factory_curated/ JSON (git-committed backup + prod sync).",
            "python manage.py export_factory_curated",
        ),
        (
            "import_factory_curated",
            "Upsert curated factory exercises/playlists from data/factory_curated/ (dry-run without --update; never deletes).",
            "python manage.py import_factory_curated --update",
        ),
        (
            "generate_transpositions",
            "Batch-create transposed copies of a UMTO chordal exercise (runtime playlist transposition does not apply to UMTO chordal rows).",
            "python manage.py generate_transpositions --exercise EA0001 --keys C,G,Bb,F#m --playlist 'My set (all keys)'",
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
