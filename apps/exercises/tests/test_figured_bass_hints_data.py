"""Sync test for the generated figured_bass_hints_data.js.

The generated JS lookup must mirror the Python source of truth:
``figures.py:_SHORTHANDS`` and ``figure_realization.py``'s ``required_numbers``
computation. Python remains the source of truth; JS drift fails CI.

Precedent: ``test_unit_allowed_answers.py::test_generated_js_matches_loader``
(codegen-and-diff pattern).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from apps.exercises.harmonization import figure_realization as fr
from apps.exercises.harmonization.figures import _SHORTHANDS, _parse_token, expand_figure_string
from apps.exercises.management.commands.build_figured_bass_lookup import _POLICIES

# apps/exercises/tests/test_figured_bass_hints_data.py -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATED_JS = _REPO_ROOT / "lab/static/js/src/config/figured_bass_hints_data.js"
_POLICY = {"min": 3, "max": 4}
_POLICY_KEY = f"{_POLICY['min']}-{_POLICY['max']}"


def _parse_generated_js():
    """Parse the ``export default {...}`` ESM shape emitted by the generator."""
    text = _GENERATED_JS.read_text()
    match = re.search(r"export\s+default\s+(\{.*\});\s*$", text, re.DOTALL)
    assert match, "generated module does not match expected ESM `export default` shape"
    return json.loads(match.group(1))


def _present_and_altered(figure):
    present, altered = set(), set()
    for raw in expand_figure_string(figure):
        tok = _parse_token(raw)
        present.add(tok.number)
        if tok.accidental or tok.quality_alter:
            altered.add(tok.number)
    return present, frozenset(altered)


def _expected_required_by_figure():
    expected = {}
    for figure in sorted(_SHORTHANDS):
        present, altered = _present_and_altered(figure)
        prototype, _ = fr.normalize(figure)
        if prototype is None:
            req = sorted(present)
        else:
            req = sorted(fr.required_numbers(prototype, _POLICY, present=present, altered=altered))
        expected[figure] = {_POLICY_KEY: req}
    return expected


def test_generated_js_matches_python_source():
    """Regenerate, then diff both lookups against live Python output."""
    subprocess.run(
        [sys.executable, "manage.py", "build_figured_bass_lookup"],
        cwd=_REPO_ROOT,
        check=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "harmony.settings.local"},
    )
    parsed = _parse_generated_js()
    assert parsed["_SHORTHANDS"] == {k: list(_SHORTHANDS[k]) for k in sorted(_SHORTHANDS)}
    assert parsed["_REQUIRED_NUMBERS_BY_FIGURE"] == _expected_required_by_figure()


def test_shorthands_mirror_is_exact():
    """The JS _SHORTHANDS is a direct mirror of figures.py:_SHORTHANDS."""
    parsed = _parse_generated_js()
    for figure, tokens in _SHORTHANDS.items():
        assert parsed["_SHORTHANDS"][figure] == list(tokens), f"_SHORTHANDS drift for {figure!r}"


def test_required_numbers_distinguishing_example_per_voice_count():
    """Distinguishing example (AGENTS.md canon rule): the required set depends
    on voice-count policy, not just the figure.

    6/4 at {2,2}: no realizable TABLE cell -> fail-safe -> both 6 and 4 required.
    6   at {2,2}: 6/3 prototype's 2-voice cell is {6} -> only 6 required, 3 omittable.

    This separates the correct per-voice-count rule from the plausible shortcut
    "all named intervals are required." {2,2} is not in the generated table (the
    corpus uses {3,4}); the underlying rule is exercised by calling
    required_numbers() directly.
    """
    policy_2 = {"min": 2, "max": 2}
    # 6/4 -> prototype 6/4, present {4,6}
    present_64, altered_64 = {4, 6}, frozenset()
    req_64 = fr.required_numbers("6/4", policy_2, present=present_64, altered=altered_64)
    assert req_64 == {4, 6}, f"6/4 at 2 voices should be fail-safe all-required, got {req_64}"

    # 6 -> prototype 6/3, present {3,6}
    present_6, altered_6 = {3, 6}, frozenset()
    req_6 = fr.required_numbers("6/3", policy_2, present=present_6, altered=altered_6)
    assert req_6 == {6}, f"6 at 2 voices should require only 6 (3 omittable), got {req_6}"

    # The two must differ -- proves the rule is per-voice-count, not "all named".
    assert req_64 != req_6


def test_altered_tone_is_always_required():
    """An altered interval (e.g. #6) is always required, even when the bare
    prototype would omit its number. Distinguishing example for the altered-tone
    rule: 6 at {3,4} requires {3,6} (both), and #6 likewise -- but the altered
    rule matters for figures like #6/5 where 5 is required-altered vs 6/5 where
    the TABLE already requires 5. The key invariant: an altered number is never
    in the omittable set."""
    for figure in ("#6", "b6", "#6/5", "#6/5°"):
        present, altered = _present_and_altered(figure)
        prototype, _ = fr.normalize(figure)
        assert prototype is not None, f"{figure!r} should map to a prototype"
        req = fr.required_numbers(prototype, _POLICY, present=present, altered=altered)
        # every altered tone that is present must be in required
        assert set(altered) & present <= req, (
            f"{figure!r}: altered tones {set(altered) & present} not all required (got {req})"
        )


def test_octave_required_only_in_failsafe_figures():
    """Octave (8) is included in required_numbers only for fail-safe figures
    (those without a TABLE prototype) when 8 is present in the figure tokens.
    For figures with a TABLE prototype, octave is handled by required_numbers()
    and may or may not be required depending on voice-count policy."""
    from apps.exercises.harmonization import figure_realization as fr

    parsed = _parse_generated_js()
    for figure, by_policy in parsed["_REQUIRED_NUMBERS_BY_FIGURE"].items():
        prototype, _ = fr.normalize(figure)
        expanded = expand_figure_string(figure)
        has_octave_token = "8" in expanded

        for policy_key, nums in by_policy.items():
            octave_in_required = 8 in nums

            if prototype is None:
                # Fail-safe figures: octave is required if it was in the figure
                if has_octave_token:
                    assert octave_in_required, (
                        f"{figure!r} {policy_key}: fail-safe with octave token should "
                        f"require 8, got {nums}"
                    )
            else:
                # TABLE-based figures: octave should never be in required
                # (the TABLE prototype handles intervals, octave is only optional doubling)
                assert not octave_in_required, (
                    f"{figure!r} {policy_key}: TABLE-based figure should not require "
                    f"octave, got {nums}"
                )


def test_present_policies_are_well_formed():
    """_POLICIES itself is well-formed (int min/max, min<=max). The live-corpus
    drift check (does every voiceCountPolicy shape actually stored on
    Exercise rows appear in _POLICIES) runs inside the
    build_figured_bass_lookup management command itself, not here -- this is
    a plain pytest module (no django_db fixture, no test-DB isolation) and
    querying Exercise.objects would either error for lack of DB access or,
    if given DB access, only ever see the empty/fixture-only pytest test
    database, never the real corpus this check needs to observe."""
    for policy in _POLICIES:
        assert int(policy.get("min", 3)) <= int(policy.get("max", 4))