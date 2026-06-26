"""Theory parity & characterization gate — both engines pinned to expert goldens.

Goldens live in repo-root theory_golden/*.json and are loaded by both this
Python suite and the Node tests (theory_golden/*.test.js). See
docs/superpowers/specs/2026-06-26-theory-parity-harness-design.md.
"""
import json
from pathlib import Path

import pytest

_GOLDEN_DIR = Path(__file__).resolve().parents[3] / "theory_golden"


def _load_golden(name: str) -> list[dict]:
    with open(_GOLDEN_DIR / name, encoding="utf-8") as f:
        return json.load(f)["cases"]


def _ids(cases: list[dict]) -> list[str]:
    return [c["id"] for c in cases]


# --- Parity: spelling -------------------------------------------------------

_SPELLING_CASES = _load_golden("spelling.json")


@pytest.mark.parametrize("case", _SPELLING_CASES, ids=_ids(_SPELLING_CASES))
def test_spelling_parity_python(case):
    from apps.exercises.harmonization.figures import spelling_for_pc_in_key

    key = case["input"]["key"]
    actual = {
        str(midi): spelling_for_pc_in_key(key, midi % 12)
        for midi in case["input"]["midis"]
    }
    assert actual == case["expected"]["spelling"]
