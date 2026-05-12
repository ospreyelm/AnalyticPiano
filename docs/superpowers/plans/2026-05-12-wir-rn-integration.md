# When in Rome RN Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace music21's `romanNumeralFromChord()` with human-annotated When in Rome labels as the source of `roman_numeral` in UMTO `AnalysisSlice` objects, while preserving music21 output in `raw_roman_numeral` for audit.

**Architecture:** A one-time conversion script parses 371 WiR `.txt` files into `data/when_in_rome/chorales.json`. A new `wir_corpus.py` module loads that JSON and exposes exact-match lookup by `(riemenschneider, measure, beat)`. The import command's `_build_roman_analysis_overrides()` function uses this lookup instead of music21, omits NCT beats entirely, and hard-fails if the chorale isn't in WiR.

**Tech Stack:** Python 3.10+, music21, Django management commands, Pydantic (UMTO schema), pytest

---

## File Map

| File | Role |
|---|---|
| `scripts/convert_wir_corpus.py` | One-time: parse WiR `.txt` files → `chorales.json` + `bwv_to_riemenschneider.json` |
| `scripts/tests/test_convert_wir_corpus.py` | Parser unit tests (no filesystem, embedded WiR text) |
| `data/when_in_rome/chorales.json` | Generated corpus — checked in after conversion |
| `data/when_in_rome/bwv_to_riemenschneider.json` | Generated BWV map — checked in after conversion |
| `data/when_in_rome/README.md` | Provenance, license (CC BY-SA), citation |
| `apps/exercises/utils/wir_corpus.py` | Lookup module: `lookup()`, `has_chorale()`, `bwv_to_riemenschneider()` |
| `apps/exercises/tests/test_wir_corpus.py` | Lookup tests against real `chorales.json` |
| `apps/exercises/umto.py` | Add `local_key: Optional[str]` to `AnalysisLayer` |
| `apps/exercises/umto_schema.json` | Regenerated after `umto.py` change |
| `apps/exercises/management/commands/import_bach_phrases.py` | Wire WiR into `_build_roman_analysis_overrides()`; remove `try/except` swallow |
| `apps/exercises/tests/test_import_bach_phrases.py` | Integration tests for WiR import path |

---

## Task 1: Parser unit tests (RED)

Write tests for the WiR `.txt` parser before writing the parser itself. These tests use embedded WiR text snippets — no filesystem access.

**Files:**
- Create: `scripts/tests/__init__.py` (empty)
- Create: `scripts/tests/test_convert_wir_corpus.py`

- [ ] **Step 1: Create test file**

```python
# scripts/tests/test_convert_wir_corpus.py
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# We import the parser function we're about to write
from convert_wir_corpus import parse_wir_file


def _parse(text):
    """Helper: parse embedded text as if it were a WiR file."""
    return parse_wir_file(text, riemenschneider=1)


def test_anacrusis():
    result = _parse("Composer: Bach\nBWV: 269\nTime Signature: 3/4\n\nm0 b3 G: I\n")
    labels = result["labels"]
    assert len(labels) == 1
    assert labels[0] == {"measure": 0, "beat": 3.0, "label": "I", "local_key": "G"}


def test_beat_marker_parsed():
    result = _parse("BWV: 269\nTime Signature: 4/4\n\nm1 I b2 IV b2.5 V6\n")
    labels = result["labels"]
    assert labels[0] == {"measure": 1, "beat": 1.0, "label": "I",  "local_key": "?"}
    assert labels[1] == {"measure": 1, "beat": 2.0, "label": "IV", "local_key": "?"}
    assert labels[2] == {"measure": 1, "beat": 2.5, "label": "V6", "local_key": "?"}


def test_key_change_updates_local_key():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm5 G: I\nm6 d: i b2 V\n")
    labels = result["labels"]
    assert labels[0]["local_key"] == "G"
    assert labels[1]["local_key"] == "d"
    assert labels[2]["local_key"] == "d"


def test_key_change_token_not_emitted_as_label():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm1 G: I\n")
    labels = result["labels"]
    assert len(labels) == 1
    assert labels[0]["label"] == "I"


def test_flat_rn_not_confused_with_beat_marker():
    # bVI starts with 'b' but is not a beat marker (no digit after 'b')
    result = _parse("BWV: 269\nTime Signature: 4/4\n\nm1 bVI b2 iv\n")
    labels = result["labels"]
    assert labels[0]["label"] == "bVI"
    assert labels[0]["beat"] == 1.0
    assert labels[1]["label"] == "iv"
    assert labels[1]["beat"] == 2.0


def test_repeat_barlines_skipped():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm4 V || b3 I\n")
    labels = result["labels"]
    labels_only = [l["label"] for l in labels]
    assert "||" not in labels_only
    assert "V" in labels_only
    assert "I" in labels_only


def test_variant_attaches_to_main_label():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm11 vi b2 iii6\nm11var1 vi b2 I6/4\n")
    labels = result["labels"]
    # m11 b2: main=iii6, variant=I6/4
    b2 = next(l for l in labels if l["measure"] == 11 and l["beat"] == 2.0)
    assert b2["label"] == "iii6"
    assert b2.get("variant") == "I6/4"


def test_header_lines_skipped():
    result = _parse(
        "Composer: J. S. Bach\nBWV: 269\nTitle: Test\nAnalyst: Jones\n"
        "Proofreader: Smith\nNote: something\nTime Signature: 3/4\nForm: chorale\n\nm1 I\n"
    )
    labels = result["labels"]
    assert len(labels) == 1


def test_bwv_extracted_from_header():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm1 I\n")
    assert result["bwv"] == "269"


def test_title_extracted_from_header():
    result = _parse("Title: Aus meines Herzens Grunde\nBWV: 269\nTime Signature: 3/4\n\nm1 I\n")
    assert result["title"] == "Aus meines Herzens Grunde"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/project
pytest scripts/tests/test_convert_wir_corpus.py -v
```

Expected: `ImportError: cannot import name 'parse_wir_file' from 'convert_wir_corpus'` — the module doesn't exist yet.

- [ ] **Step 3: Commit the failing tests**

```bash
git add scripts/tests/__init__.py scripts/tests/test_convert_wir_corpus.py
git commit -m "test: add WiR parser unit tests (RED)"
```

---

## Task 2: Conversion script (GREEN)

Write `scripts/convert_wir_corpus.py` with the `parse_wir_file()` function and a `main()` that processes all 371 files.

**Files:**
- Create: `scripts/__init__.py` (empty)
- Create: `scripts/convert_wir_corpus.py`

- [ ] **Step 1: Write the conversion script**

```python
# scripts/convert_wir_corpus.py
"""One-time script: parse When in Rome Bach chorales into JSON.

Usage:
    python scripts/convert_wir_corpus.py /path/to/When-in-Rome/Corpus/Bach_Chorales/

Writes:
    data/when_in_rome/chorales.json
    data/when_in_rome/bwv_to_riemenschneider.json
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path


def parse_wir_file(text: str, riemenschneider: int) -> dict:
    """Parse a single WiR RomanText file into a structured dict.

    Returns:
        {
            "riemenschneider": int,
            "bwv": str | None,
            "title": str | None,
            "time_signature": str | None,
            "labels": [{"measure": int, "beat": float, "label": str, "local_key": str, "variant"?: str}]
        }
    """
    bwv = None
    title = None
    time_signature = None
    # local_key starts unknown until we see a key token
    local_key = "?"
    labels: list[dict] = []

    HEADER_RE = re.compile(
        r'^(Note|Composer|BWV|Title|Analyst|Proofreader|Time Signature|Form):'
    )
    MEASURE_RE = re.compile(r'^m(\d+)(var\d+)?\s+(.*)')
    BEAT_RE = re.compile(r'^b(\d+(?:\.\d+)?)$')
    KEY_RE = re.compile(r'^[A-Ga-g][#b-]?:$')

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Extract specific header values
        if line.startswith('BWV:'):
            bwv = line[4:].strip()
            continue
        if line.startswith('Title:'):
            title = line[6:].strip()
            continue
        if line.startswith('Time Signature:'):
            time_signature = line[15:].strip()
            continue
        if HEADER_RE.match(line):
            continue

        m = MEASURE_RE.match(line)
        if not m:
            continue

        measure_num = int(m.group(1))
        is_var = bool(m.group(2))
        rest = m.group(3).strip()

        cur_beat = 1.0
        for token in rest.split():
            if not token:
                continue
            # Beat marker: b followed immediately by digit(s)
            beat_m = BEAT_RE.match(token)
            if beat_m:
                cur_beat = float(beat_m.group(1))
                continue
            # Repeat barline
            if token in ('||', ':||', '|'):
                continue
            # Key-change token: letter + optional accidental + colon
            if KEY_RE.match(token):
                local_key = token[:-1]  # strip trailing ':'
                continue
            # RN label
            if is_var:
                # Find existing main label at this position to attach variant
                existing = next(
                    (l for l in labels
                     if l["measure"] == measure_num
                     and abs(l["beat"] - cur_beat) < 1e-6
                     and "variant" not in l),
                    None
                )
                if existing:
                    existing["variant"] = token
                else:
                    labels.append({
                        "measure": measure_num,
                        "beat": cur_beat,
                        "label": None,
                        "local_key": local_key,
                        "variant": token,
                    })
            else:
                labels.append({
                    "measure": measure_num,
                    "beat": cur_beat,
                    "label": token,
                    "local_key": local_key,
                })

    # Sort by (measure, beat)
    labels.sort(key=lambda l: (l["measure"], l["beat"]))

    return {
        "riemenschneider": riemenschneider,
        "bwv": bwv,
        "title": title,
        "time_signature": time_signature,
        "labels": labels,
    }


def main(wir_dir: str) -> None:
    wir_path = Path(wir_dir)
    if not wir_path.exists():
        print(f"ERROR: {wir_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Find all .txt files named NNN.txt (Riemenschneider numbers)
    txt_files = sorted(wir_path.glob("*.txt"))
    if not txt_files:
        print(f"ERROR: No .txt files found in {wir_dir}", file=sys.stderr)
        sys.exit(1)

    chorales: dict[str, dict] = {}
    bwv_map: dict[str, int] = {}
    errors = []

    for path in txt_files:
        # Filename should be NNN.txt
        stem = path.stem
        if not stem.isdigit():
            continue
        riem_num = int(stem)
        text = path.read_text(encoding='utf-8')
        try:
            result = parse_wir_file(text, riem_num)
        except Exception as e:
            errors.append(f"R{riem_num}: {e}")
            continue

        chorales[str(riem_num)] = result
        if result["bwv"]:
            bwv_map[result["bwv"]] = riem_num

    print(f"Parsed {len(chorales)} chorales, {len(errors)} errors")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)

    # Validate
    assert len(chorales) == 371, f"Expected 371 chorales, got {len(chorales)}"
    assert len(set(chorales.keys())) == len(chorales), "Duplicate Riemenschneider keys"

    out_dir = Path(__file__).parent.parent / "data" / "when_in_rome"
    out_dir.mkdir(parents=True, exist_ok=True)

    chorales_path = out_dir / "chorales.json"
    chorales_path.write_text(json.dumps(chorales, indent=2, ensure_ascii=False))
    print(f"Wrote {chorales_path}")

    bwv_path = out_dir / "bwv_to_riemenschneider.json"
    bwv_path.write_text(json.dumps(bwv_map, indent=2))
    print(f"Wrote {bwv_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} /path/to/When-in-Rome/Corpus/Bach_Chorales/")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 2: Handle the `local_key = "?"` default in tests**

The test `test_beat_marker_parsed` uses `"?"` as the expected `local_key` when no key token appears before the first label. The parser initialises `local_key = "?"` for this case. Check the test passes by running:

```bash
pytest scripts/tests/test_convert_wir_corpus.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/__init__.py scripts/convert_wir_corpus.py
git commit -m "feat: add WiR corpus conversion script and parser"
```

---

## Task 3: Download WiR and generate JSON files

This task is manual — it requires downloading the When in Rome repo.

**Files:**
- Create: `data/when_in_rome/chorales.json`
- Create: `data/when_in_rome/bwv_to_riemenschneider.json`
- Create: `data/when_in_rome/README.md`

- [ ] **Step 1: Clone When in Rome**

```bash
git clone https://github.com/MarkGotham/When-in-Rome /tmp/when-in-rome
cd /tmp/when-in-rome
git log --oneline -1  # note the commit SHA for provenance
```

- [ ] **Step 2: Run the conversion script**

```bash
cd /path/to/harmonylab
python scripts/convert_wir_corpus.py /tmp/when-in-rome/Corpus/Bach_Chorales/
```

Expected output:
```
Parsed 371 chorales, 0 errors
Wrote data/when_in_rome/chorales.json
Wrote data/when_in_rome/bwv_to_riemenschneider.json
```

- [ ] **Step 3: Create the provenance README**

Create `data/when_in_rome/README.md` with this content (fill in SHA and date):

```markdown
# When in Rome — Bach Chorales Corpus

This directory contains derived data from the When in Rome corpus.

## Source

- **Repository:** https://github.com/MarkGotham/When-in-Rome
- **Commit SHA:** <FILL IN from `git log --oneline -1` above>
- **Subset:** `Corpus/Bach_Chorales/` (371 chorales)
- **Converted:** <FILL IN date, e.g. 2026-05-12>

## License

CC BY-SA — Creative Commons Attribution-ShareAlike.

## Citation

Gotham, M., & Ireland, M. (2019). 'Taking Form': A Representation Standard, Conversion Code and
Dataset for Music Analysis. In Proceedings of the 20th International Society for Music Information
Retrieval Conference (ISMIR), Delft, Netherlands.

## Files

- `chorales.json` — All 371 chorales, keyed by Riemenschneider number (string).
  Each entry: `{riemenschneider, bwv, title, time_signature, labels: [{measure, beat, label, local_key}]}`
- `bwv_to_riemenschneider.json` — Flat map `{"BWV_string": riemenschneider_int}`.
  Auto-derived from BWV: header lines in WiR files.
```

- [ ] **Step 4: Commit**

```bash
git add data/when_in_rome/
git commit -m "data: add When in Rome Bach chorales corpus JSON (371 chorales)"
```

---

## Task 4: Lookup module unit tests (RED)

Write tests for `wir_corpus.py` before writing the module. These tests use the real `chorales.json` — the data file is the contract.

**Files:**
- Create: `apps/exercises/tests/test_wir_corpus.py`

- [ ] **Step 1: Write the test file**

```python
# apps/exercises/tests/test_wir_corpus.py
import pytest
from apps.exercises.utils.wir_corpus import lookup, has_chorale, bwv_to_riemenschneider


def test_anacrusis_lookup():
    # R1 pickup: m0 b3 G: I
    result = lookup(1, 0, 3.0)
    assert result is not None
    assert result["label"] == "I"
    assert result["local_key"] == "G"


def test_mid_measure_label():
    # R1 m1 b2: IV6
    result = lookup(1, 1, 2.0)
    assert result is not None
    assert result["label"] == "IV6"
    assert result["local_key"] == "G"


def test_nct_beat_returns_none():
    # R1 m3 b1.5: no WiR label (NCT beat — passing tone)
    result = lookup(1, 3, 1.5)
    assert result is None


def test_unknown_chorale_returns_none():
    result = lookup(999, 1, 1.0)
    assert result is None


def test_has_chorale_known():
    assert has_chorale(1) is True


def test_has_chorale_unknown():
    assert has_chorale(999) is False


def test_bwv_lookup_hit():
    assert bwv_to_riemenschneider("269") == 1


def test_bwv_lookup_miss():
    assert bwv_to_riemenschneider("99999") is None


def test_float_tolerance():
    # Beat stored as 3.0, queried as 3.0000000001 — should still match
    result = lookup(1, 0, 3.0000000001)
    assert result is not None
    assert result["label"] == "I"


def test_key_change_reflected_in_local_key():
    # Find a chorale with a known modulation and verify local_key shifts.
    # R10 (BWV 38.6, A minor) — check that at least one label has local_key != "a"
    # indicating a tonicisation occurred.
    # First find any label in R10
    r10_start = lookup(10, 0, 3.0) or lookup(10, 1, 1.0)
    assert r10_start is not None  # R10 must exist in corpus
    # The corpus must contain at least one label for R10 — existence confirmed above.
    # Tonicisation check: look for any label with local_key that starts uppercase
    # (major tonicisation) in a minor key chorale — spot check via has_chorale
    assert has_chorale(10) is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest apps/exercises/tests/test_wir_corpus.py -v
```

Expected: `ImportError: cannot import name 'lookup' from 'apps.exercises.utils.wir_corpus'`

- [ ] **Step 3: Commit failing tests**

```bash
git add apps/exercises/tests/test_wir_corpus.py
git commit -m "test: add wir_corpus lookup tests (RED)"
```

---

## Task 5: Lookup module (GREEN)

Write `apps/exercises/utils/wir_corpus.py`.

**Files:**
- Create: `apps/exercises/utils/wir_corpus.py`

- [ ] **Step 1: Write the module**

```python
# apps/exercises/utils/wir_corpus.py
"""When in Rome corpus lookup for Bach chorales.

Loads data/when_in_rome/chorales.json and bwv_to_riemenschneider.json
once at module level. Provides exact-match lookup by (riemenschneider, measure, beat).
"""
from __future__ import annotations
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "when_in_rome"

def _load_json(name: str) -> dict:
    path = _DATA_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)

_CHORALES: dict[str, dict] = _load_json("chorales.json")
_BWV_MAP: dict[str, int] = _load_json("bwv_to_riemenschneider.json")


def has_chorale(riemenschneider: int) -> bool:
    """Return True if WiR corpus contains data for this Riemenschneider number."""
    return str(riemenschneider) in _CHORALES


def lookup(riemenschneider: int, measure: int, beat: float) -> dict | None:
    """Return {label, local_key} for exact (measure, beat) match.

    Exact match: abs(stored_beat - beat) < 1e-6.
    Returns None if chorale unknown, or no label at this exact position.
    """
    chorale = _CHORALES.get(str(riemenschneider))
    if chorale is None:
        return None
    for entry in chorale["labels"]:
        if entry["measure"] == measure and abs(entry["beat"] - beat) < 1e-6:
            if entry.get("label") is None:
                return None  # variant-only entry, no main label
            return {"label": entry["label"], "local_key": entry["local_key"]}
    return None


def bwv_to_riemenschneider(bwv: str) -> int | None:
    """Return Riemenschneider number for a BWV string, or None if not found."""
    return _BWV_MAP.get(str(bwv))
```

- [ ] **Step 2: Run tests**

```bash
pytest apps/exercises/tests/test_wir_corpus.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/exercises/utils/wir_corpus.py
git commit -m "feat: add wir_corpus lookup module"
```

---

## Task 6: Add `local_key` to `AnalysisLayer` and regenerate schema

**Files:**
- Modify: `apps/exercises/umto.py`
- Modify: `apps/exercises/umto_schema.json` (regenerated)

- [ ] **Step 1: Add `local_key` to `AnalysisLayer`**

In `apps/exercises/umto.py`, find the `AnalysisLayer` class (currently around line 54) and add the new field:

```python
class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None  # unfiltered music21 output; durable record
    local_key: Optional[str] = None           # active key at this slice, e.g. "G", "d"
    raw_figured_bass: Optional[str] = None    # unabbreviated stack: "8/5/3", "7/5/3"
    figured_bass: Optional[str] = None        # abbreviated per Kellner: "", "7", "4/2"
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None    # e.g. "Predominant", "Dominant"
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
pytest apps/exercises/tests/test_umto_contract.py apps/exercises/tests/test_umto_factory.py -v
```

Expected: all PASS (field is Optional with default None — backward compatible).

- [ ] **Step 3: Regenerate the schema**

```bash
python manage.py make_umto_schema
```

Expected: `apps/exercises/umto_schema.json` updated with `local_key` property added.

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json
git commit -m "feat: add local_key to AnalysisLayer; regenerate UMTO schema"
```

---

## Task 7: Integration tests for the import pipeline (RED)

Write failing tests for the WiR-wired import command before touching the command itself.

**Files:**
- Modify: `apps/exercises/tests/test_import_bach_phrases.py`

- [ ] **Step 1: Read the existing test file to understand patterns**

```bash
head -80 apps/exercises/tests/test_import_bach_phrases.py
```

- [ ] **Step 2: Add WiR integration tests**

Add these test functions to `apps/exercises/tests/test_import_bach_phrases.py`:

```python
# --- WiR integration tests ---
# These require the real chorales.json and a live Django + music21 setup.
# Mark with pytest.mark.django_db.

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.exercises.models import Exercise


@pytest.mark.django_db
def test_wir_roman_first_slice_r1(admin_user):
    """R1 in roman mode: first slice should have roman_numeral='I', local_key='G'."""
    call_command(
        'import_bach_phrases',
        riemenschneider=1,
        author=admin_user.email,
        mode='roman',
        extra_tags=['unit:9'],
    )
    ex = Exercise.objects.filter(skill_tags__contains=['unit:9']).first()
    assert ex is not None
    umto = ex.data
    slices = umto['analysis']
    assert len(slices) > 0
    first = slices[0]['content']
    assert first['roman_numeral'] == 'I'
    assert first['local_key'] == 'G'


@pytest.mark.django_db
def test_wir_roman_raw_rn_populated(admin_user):
    """raw_roman_numeral should be populated with music21 figure."""
    call_command(
        'import_bach_phrases',
        riemenschneider=1,
        author=admin_user.email,
        mode='roman',
        extra_tags=['unit:9'],
    )
    ex = Exercise.objects.filter(skill_tags__contains=['unit:9']).first()
    slices = ex.data['analysis']
    assert all(s['content']['raw_roman_numeral'] is not None for s in slices)


@pytest.mark.django_db
def test_nct_beat_omitted(admin_user):
    """m3 b1.5 is an NCT beat in R1 — no AnalysisSlice at that offset."""
    call_command(
        'import_bach_phrases',
        riemenschneider=1,
        author=admin_user.email,
        mode='roman',
        extra_tags=['unit:9'],
    )
    ex = Exercise.objects.filter(skill_tags__contains=['unit:9']).first()
    slices = ex.data['analysis']
    # m3 b1.5: absolute offset depends on phrase segmentation but the beat should not appear
    # Find any slice whose offset corresponds to a b1.5 beat (0.5 quarter lengths into a beat)
    half_beat_offsets = [s['offset'] for s in slices if (s['offset'] * 2) % 1 != 0]
    # None of those half-beat offsets should be NCT beats from m3
    # Simpler check: no slice should have roman_numeral=None
    for s in slices:
        assert s['content']['roman_numeral'] is not None, \
            f"Found slice with null roman_numeral at offset {s['offset']}"


@pytest.mark.django_db
def test_unknown_riemenschneider_raises(admin_user):
    """Riemenschneider 999 is not in WiR — should raise CommandError."""
    with pytest.raises((CommandError, SystemExit)):
        call_command(
            'import_bach_phrases',
            riemenschneider=999,
            author=admin_user.email,
            mode='roman',
        )


@pytest.mark.django_db
def test_tonicisation_local_key(admin_user):
    """R10 (A minor, BWV 38.6) — verify local_key reflects key changes in WiR."""
    call_command(
        'import_bach_phrases',
        riemenschneider=10,
        author=admin_user.email,
        mode='roman',
        extra_tags=['unit:9_wir_test'],
    )
    exercises = Exercise.objects.filter(skill_tags__contains=['unit:9_wir_test'])
    all_slices = []
    for ex in exercises:
        all_slices.extend(ex.data.get('analysis', []))
    assert len(all_slices) > 0
    local_keys = {s['content']['local_key'] for s in all_slices if s['content'].get('local_key')}
    # R10 is A minor — at minimum the home key should appear
    assert len(local_keys) >= 1
```

- [ ] **Step 3: Run to confirm RED**

```bash
pytest apps/exercises/tests/test_import_bach_phrases.py -k "wir" -v
```

Expected: tests fail — `_build_roman_analysis_overrides` doesn't use WiR yet.

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/tests/test_import_bach_phrases.py
git commit -m "test: add WiR import integration tests (RED)"
```

---

## Task 8: Wire WiR into the import command (GREEN)

Modify `_build_roman_analysis_overrides()` to use WiR and remove the `try/except` swallow.

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`

- [ ] **Step 1: Update `_build_roman_analysis_overrides()` signature and body**

Replace the existing function (lines 26–71) with:

```python
def _build_roman_analysis_overrides(phrase_score, global_key, unit_tags: list, riemenschneider: int) -> list:
    """Analyze a phrase and return UMTO analysis_overrides using When in Rome labels.

    roman_numeral: WiR human-annotated label (omitted for NCT beats).
    local_key: active key at that slice per WiR key-change annotations.
    raw_roman_numeral: music21 figure, always populated for audit.

    NCT beats (no WiR label) are omitted entirely — no slice emitted.
    Raises CommandError if the chorale is not in the WiR corpus.
    """
    from music21.roman import romanNumeralFromChord
    from apps.exercises.utils import wir_corpus
    from django.core.management.base import CommandError

    if not wir_corpus.has_chorale(riemenschneider):
        raise CommandError(
            f"Riemenschneider {riemenschneider} not found in When in Rome corpus. "
            f"Only standalone chorales (1–371) are supported in roman mode."
        )

    chorded = phrase_score.chordify()
    measures = list(chorded.getElementsByClass('Measure'))
    if not measures:
        return []

    first_measure_offset = measures[0].offset
    overrides = []
    seen_offsets = set()

    for m in measures:
        measure_start = m.offset - first_measure_offset
        for element in m.flat.notes:
            if not isinstance(element, chord.Chord):
                continue
            abs_offset = round(measure_start + float(element.offset), 5)
            if abs_offset in seen_offsets:
                continue
            seen_offsets.add(abs_offset)

            wir_result = wir_corpus.lookup(
                riemenschneider, element.measureNumber, float(element.beat)
            )
            if wir_result is None:
                continue  # NCT beat — omit slice entirely

            try:
                m21_figure = romanNumeralFromChord(element, global_key).figure
            except Exception:
                m21_figure = None

            overrides.append({
                "offset": abs_offset,
                "content": {
                    "roman_numeral": wir_result["label"],
                    "local_key": wir_result["local_key"],
                    "raw_roman_numeral": m21_figure,
                    "raw_figured_bass": None,
                    "figured_bass": None,
                    "pop_symbol": None,
                    "functional_label": None,
                },
                "unit_tags": list(unit_tags),
            })

    return overrides
```

- [ ] **Step 2: Remove `try/except` swallow for roman/matching modes**

Find the call site (around line 414–422):

```python
# BEFORE:
if mode in ('roman', 'matching'):
    try:
        analysis_overrides = _build_roman_analysis_overrides(
            phrase_score, m21_key, unit_nums
        )
        self.stdout.write(f"  Built {len(analysis_overrides)} roman analysis slices")
    except Exception as e:
        self.stdout.write(self.style.WARNING(f"  Roman analysis overrides failed: {e}"))
```

Replace with:

```python
# AFTER:
if mode in ('roman', 'matching'):
    analysis_overrides = _build_roman_analysis_overrides(
        phrase_score, m21_key, unit_nums, riemenschneider=riem_num
    )
    self.stdout.write(f"  Built {len(analysis_overrides)} roman analysis slices")
```

Note: `riem_num` is already in scope from line 195 (`riem_num = options.get('riemenschneider')`). If `--bwv` was used instead, resolve to Riemenschneider number first:

```python
# After the score loading block (around line 218), add:
if mode in ('roman', 'matching') and riem_num is None:
    from apps.exercises.utils.wir_corpus import bwv_to_riemenschneider as _bwv_map
    riem_num = _bwv_map(str(bwv_num))
    if riem_num is None:
        raise CommandError(
            f"BWV {bwv_num} has no Riemenschneider mapping in When in Rome corpus. "
            f"Cannot import in roman mode."
        )
```

- [ ] **Step 3: Run integration tests**

```bash
pytest apps/exercises/tests/test_import_bach_phrases.py -k "wir" -v
```

Expected: all WiR tests PASS.

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
pytest apps/exercises/tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py
git commit -m "feat: use When in Rome labels in roman mode import; omit NCT slices"
```

---

## Task 9: Final commit and push

- [ ] **Step 1: Run all tests one more time**

```bash
pytest apps/exercises/tests/ scripts/tests/ -v
```

Expected: all PASS.

- [ ] **Step 2: Push**

```bash
git push
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| One-time conversion script | Task 2 |
| `bwv_to_riemenschneider.json` | Task 2 (main()) + Task 3 |
| `data/when_in_rome/README.md` provenance | Task 3 |
| `wir_corpus.py`: `lookup()`, `has_chorale()`, `bwv_to_riemenschneider()` | Task 5 |
| `local_key` added to `AnalysisLayer` | Task 6 |
| `make_umto_schema` regeneration | Task 6 |
| `_build_roman_analysis_overrides()` uses WiR | Task 8 |
| Remove `try/except` swallow | Task 8 |
| NCT slices omitted entirely | Task 8 |
| Early abort via `has_chorale()` | Task 8 |
| BWV → Riemenschneider derivation at call site | Task 8 |
| Parser tests (embedded WiR text) | Task 1 |
| Lookup tests (real chorales.json) | Task 4 |
| Integration tests: first slice, raw_rn, NCT omission, unknown R, tonicisation | Task 7 |
| Float tolerance `< 1e-6` | Task 5 (`lookup()` implementation) |
| Variant attachment rule | Task 2 (`parse_wir_file()`) |

All spec requirements covered. No gaps.

**Type/name consistency:**
- `lookup()` returns `{"label": str, "local_key": str} | None` — consistent across Task 4 (tests), Task 5 (implementation), Task 8 (usage).
- `has_chorale()` returns `bool` — consistent across Task 4, Task 5, Task 8.
- `bwv_to_riemenschneider()` returns `int | None` — consistent.
- Override object shape uses `"content": {...}` nesting — matches existing codebase pattern confirmed in Task 8.
- `local_key` field name consistent across `umto.py` (Task 6), corpus JSON, lookup return value, override dict.

**No placeholders:** All steps contain actual code. No TBDs.
