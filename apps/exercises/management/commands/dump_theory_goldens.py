"""Emit candidate theory golden files for expert review.

Walks representative inputs through the current Python engines and writes
candidate cases to all four theory_golden/*.json files. New cases get empty
`reviewed_by` (blocked by the meta review-gate until an expert signs off).

Merge policy by primitive:
- spelling / figured_bass / transposition are fully machine-derivable: merged
  by `id` via _merge_by_id; `reviewed_by`/`reviewed_at` preserved, and a case
  whose recomputed `expected` drifts from a reviewed golden is flagged (stamp
  cleared) rather than silently overwritten.
- harmonization_e2e is only partly machine-derivable: _refresh_e2e recomputes
  `expected.targets` from each case's stored umto and preserves the
  expert-authored `canonical_realization`/`wrong_realizations`, clearing the
  stamp only when `targets` drift. It also seeds the EB64RV regression case
  (targets only) if the DB has the exercise and the golden lacks it.

Usage:
    python manage.py dump_theory_goldens            # write candidates
    python manage.py dump_theory_goldens --dry-run  # report only
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

_GOLDEN_DIR = Path(__file__).resolve().parents[4] / "theory_golden"


def _spelling_candidates() -> list[dict]:
    from apps.exercises.harmonization.figures import spelling_for_pc_in_key

    seeds = [
        ("spelling-bb-major-tonic-EB64RV", "jBb", [46, 70, 74, 77],
         "Bb-major bass+chord (EB64RV regression): pc 10 spells Bb not A#"),
        ("spelling-c-major-triad", "jC_", [48, 52, 55],
         "C-major tonic triad spells C E G"),
    ]
    cases = []
    for cid, key, midis, desc in seeds:
        spelling = {str(m): spelling_for_pc_in_key(key, m % 12) for m in midis}
        cases.append({
            "id": cid,
            "primitive": "spelling",
            "description": desc,
            "input": {"key": key, "midis": midis},
            "expected": {"spelling": spelling},
            "canon_ref": "music-theory-canon.md#spelling",
            "reviewed_by": "",
            "reviewed_at": "",
        })
    return cases


def _figured_bass_candidates() -> list[dict]:
    from apps.exercises.harmonization.figures import derive_required_notes

    seeds = [
        ("fb-c-major-6-3-on-E", "C", "E3", "6/3",
         "C major, bass E, figure 6/3"),
        ("fb-c-major-5-3-on-C", "C", "C3", "5/3",
         "C major, bass C, figure 5/3"),
    ]
    cases = []
    for cid, key, bass, figure, desc in seeds:
        d = derive_required_notes(key_name=key, bass_name=bass, figure=figure)
        cases.append({
            "id": cid,
            "primitive": "figured_bass",
            "description": desc,
            "input": {"key": key, "bass": bass, "figure": figure},
            "expected": {
                "required_note_names": d["required_note_names"],
                "required_upper_pcs": d["required_upper_pcs"],
                "allowed_pcs": d["allowed_pcs"],
            },
            "canon_ref": "music-theory-canon.md#figured-bass",
            "reviewed_by": "",
            "reviewed_at": "",
        })
    return cases


def _transposition_candidates() -> list[dict]:
    from apps.exercises.services.transposition_service import _transpose_chords

    seeds = [
        ("transpose-C-to-D-tonic-triad", "jC_", "jD_", 2,
         [{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67],
           "hidden": [], "spelling": ["C", "E", "G"]}],
         "C-major tonic triad up a major 2nd to D major"),
    ]
    cases = []
    for cid, src, tgt, vec, chords, desc in seeds:
        out = _transpose_chords(chords, vec, source_key_hl=src, target_key_hl=tgt)
        cases.append({
            "id": cid,
            "primitive": "transposition",
            "description": desc,
            "input": {
                "source_key": src, "target_key": tgt,
                "midi_vector": vec, "chords": chords,
            },
            "expected": {"chords": out},
            "canon_ref": "music-theory-canon.md#transposition",
            "reviewed_by": "",
            "reviewed_at": "",
        })
    return cases


# Fully machine-derivable primitives: builder owns the entire `expected`,
# so _merge_by_id can drift-check `expected` wholesale.
_BUILDERS = {
    "spelling.json": _spelling_candidates,
    "figured_bass.json": _figured_bass_candidates,
    "transposition.json": _transposition_candidates,
}


def _refresh_e2e(existing: list[dict]) -> tuple[list[dict], list[str]]:
    """Refresh harmonization_e2e goldens.

    Only `expected.targets` is machine-derivable (from `input.umto`); the
    `canonical_realization` / `wrong_realizations` lists are expert-authored
    and must be preserved. So this does NOT use _merge_by_id: for each existing
    case it recomputes `targets` from the stored umto, flagging drift (and
    clearing the review stamp) only when targets change — realizations and all
    other fields are kept verbatim. It also seeds the EB64RV regression case
    (empty realizations, blank stamp) if the DB has the exercise and the golden
    lacks it.
    """
    from apps.exercises.harmonization.targets import build_targets_from_umto
    from apps.exercises.models import Exercise

    out: list[dict] = []
    notes: list[str] = []
    seen: set[str] = set()

    for case in existing:
        seen.add(case["id"])
        umto = (case.get("input") or {}).get("umto")
        merged = json.loads(json.dumps(case))  # deep copy
        if not umto:
            out.append(merged)
            continue
        new_targets = build_targets_from_umto(umto)
        old_targets = (case.get("expected") or {}).get("targets")
        merged.setdefault("expected", {})["targets"] = new_targets
        if old_targets != new_targets:
            merged["reviewed_by"] = ""
            merged["reviewed_at"] = ""
            notes.append(f"DRIFT {case['id']} (targets changed; re-review needed)")
        out.append(merged)

    if "e2e-eb64rv-bb-major-I-V-I" not in seen:
        try:
            ex = Exercise.objects.get(id="EB64RV")
            umto = (ex.data.get("score") or {}).get("umto")
            if umto:
                out.append({
                    "id": "e2e-eb64rv-bb-major-I-V-I",
                    "primitive": "harmonization_e2e",
                    "description": "EB64RV regression (jBb, I-V-I): Bb bass spells Bb not A#",
                    "input": {"umto": umto},
                    "expected": {
                        "targets": build_targets_from_umto(umto),
                        "canonical_realization": [],
                        "wrong_realizations": [],
                    },
                    "canon_ref": "music-theory-canon.md#harmonization",
                    "reviewed_by": "",
                    "reviewed_at": "",
                })
                notes.append("NEW  e2e-eb64rv-bb-major-I-V-I "
                             "(targets seeded; realizations + review needed)")
        except Exercise.DoesNotExist:
            notes.append("SKIP EB64RV not in DB — cannot seed e2e regression case")

    return out, notes


def _merge_by_id(existing: list[dict], candidates: list[dict]) -> tuple[list[dict], list[str]]:
    """Merge candidates into existing, preserving review stamps; flag drift."""
    by_id = {c["id"]: c for c in existing}
    notes: list[str] = []
    out: list[dict] = []
    seen: set[str] = set()
    for cand in candidates:
        seen.add(cand["id"])
        prior = by_id.get(cand["id"])
        if prior is None:
            out.append(cand)
            notes.append(f"NEW  {cand['id']} (needs review)")
            continue
        merged = dict(cand)
        if prior.get("expected") == cand.get("expected"):
            # No drift: keep prior review stamps.
            merged["reviewed_by"] = prior.get("reviewed_by", "")
            merged["reviewed_at"] = prior.get("reviewed_at", "")
            out.append(merged)
        else:
            # Drift: clear stamp so the meta-gate forces re-review.
            merged["reviewed_by"] = ""
            merged["reviewed_at"] = ""
            out.append(merged)
            notes.append(f"DRIFT {cand['id']} (expected changed; re-review needed)")
    # Keep any prior cases the builder no longer emits, untouched.
    for prior in existing:
        if prior["id"] not in seen:
            out.append(prior)
    return out, notes


class Command(BaseCommand):
    help = "Emit candidate theory golden files for expert review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report new/drifted cases without writing files.",
        )

    def _process(self, fname: str) -> tuple[list[dict], list[str]]:
        """Return (merged_cases, notes) for one golden file."""
        path = _GOLDEN_DIR / fname
        existing = []
        if path.exists():
            with open(path, encoding="utf-8") as f:
                existing = json.load(f).get("cases", [])
        if fname == "harmonization_e2e.json":
            return _refresh_e2e(existing)
        return _merge_by_id(existing, _BUILDERS[fname]())

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        _GOLDEN_DIR.mkdir(exist_ok=True)
        all_files = list(_BUILDERS.keys()) + ["harmonization_e2e.json"]
        for fname in all_files:
            merged, notes = self._process(fname)
            for note in notes:
                self.stdout.write(f"  {fname}: {note}")
            if not notes:
                self.stdout.write(f"  {fname}: no changes")
            if not dry_run:
                with open(_GOLDEN_DIR / fname, "w", encoding="utf-8") as f:
                    json.dump({"cases": merged}, f, indent=2)
                    f.write("\n")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no files written."))
        else:
            self.stdout.write(self.style.SUCCESS("Candidate goldens written."))
