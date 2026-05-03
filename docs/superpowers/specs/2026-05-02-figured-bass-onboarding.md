# Figured Bass Feature — New Context Onboarding

## What we're building

A `mode:figures` parallel curriculum track alongside the existing `mode:roman` track in HarmonyLab. Same Bach chorales, same units 9–18, but the student labels figured bass instead of Roman numerals.

## What's already built (Roman numeral track — read this first)

The Roman numeral pipeline was just implemented. Key files:

- `docs/superpowers/specs/2026-05-02-taxonomy-as-source-of-truth-design.md` — the design spec
- `docs/superpowers/plans/2026-05-02-taxonomy-as-source-of-truth.md` — the implementation plan
- `music_theory_taxonomy.json` — has `analysis.roman.cumulative` and `analysis.roman.new` per unit 9–18
- `apps/exercises/taxonomy_reader.py` — `get_cumulative_values(unit_n, family)`, `get_new_values(unit_n, family)`
- `apps/exercises/umto.py` — `AnalysisLayer` has `roman_numeral`, `raw_roman_numeral`, `figured_bass` fields; `AnalysisSlice` has `is_target`
- `apps/exercises/management/commands/import_bach_phrases.py` — stores `raw_roman_numeral` (unfiltered music21); targeting at request time
- `lab/views.py` `generate_exercise_context()` — builds `analysisPolicy` payload with `allowedValues`, `newValues`, `displayMap`
- `lab/static/js/src/models/exercise_definition.js` — reads `analysisPolicy` from payload; `applySkillFilter` is server-driven

The architecture: taxonomy JSON is single source of truth → Python derives curriculum policy at request time → `analysisPolicy` object sent to browser → JS uses it for slot visibility and dropdown choices.

## Figured bass theory (teach the AI this)

**Figured bass = generic intervals above the bass note, with accidentals where non-diatonic.**

Example: chord F#3-A3-C#4-F#4 in F# minor
- F#→A = 3rd
- F#→C# = 5th  
- F#→F# = 8th (octave)
- Complete figure: `8/5/3`
- Abbreviated: nothing (implied — most common chord)

Example: chord A3-C#4-C#4-F#4
- A→C# = 3rd
- A→F# = 6th
- Complete: `6/3/3` (or `6/3`)
- Abbreviated: `6`

**Key insight:** "Inversion" is a modern term Bach didn't use. `6` just means "a sixth and a third above the bass." Whether that's "first inversion" is a later analytical interpretation. `6/4` means "a sixth and a fourth above the bass" — sometimes cadential, sometimes passing, sometimes embellishing. The figure describes the sound; Roman numerals interpret the function.

**Abbreviation rules** (from Kellner 1732 and standard practice):

| Complete figure | Abbreviated |
|----------------|-------------|
| `8/5/3` | (nothing) |
| `8/5/b3` or `8/#5/3` | `b` or `#` (accidental only) |
| `8/6/3` or `6/6/3` or `6/3/3` | `6` |
| `8/6/4` | `6/4` |
| `7/5/3` or `8/7/3` | `7` |
| `6/5/3` | `6/5` |
| `6/4/3` | `4/3` |
| `6/4/2` | `4/2` or `2` |
| `8/5/4` | `5/4` |
| `9/5/3` | `9` |
| `9/7/3` | `9/7` |
| `6/4+` (aug. sixth) | `4+` |
| `7/4/2` | nothing (suspension passing through) |

**Chromatic prefixes:** `#` = raised, `b` = lowered, relative to the diatonic scale of the key. A raised 4th above the bass = `#4`. A minor 6th in a major key = `b6`.

**Voice texture matters:** 4-voice chorales have `8/5/3`; 3-voice might show `5/3` or `8/3`; same abbreviation rules apply but fewer intervals to suppress.

## What music21 currently gives us

`romanNumeralFromChord()` appends inversion figures to the Roman numeral root — e.g. `V652` means V with figures 6/5/2. This is NOT how we want to derive figured bass — it conflates harmonic function with voicing.

The correct approach: compute generic intervals directly from pitches above bass, apply chromatic prefixes from the key, then abbreviate. We tested this:

```python
from music21 import interval
itv = interval.Interval(bass_pitch, upper_pitch)
generic = abs(itv.generic.directed)  # e.g. 3, 5, 6
spec = itv.specifier  # AUGMENTED, DIMINISHED, MAJOR, MINOR, PERFECT
```

Results on BWV17:
- `A3 C#4 E4 A4` → `8/5/3` → nothing ✓
- `F#3 C#4 F#4 A4` → `8/5/3` (octave doubling) → nothing ✓  
- `D3 G#3 B3 E4` → `#4/6/9` (augmented fourth = German sixth context) ✓

`analyze.js` has a full figured bass engine (`thoroughbass_stack`, `abbreviate_thoroughbass`) but it lacks correct spelling in some edge cases. The Python pipeline should compute figured bass fresh from pitches + key using music21's interval machinery.

## Curriculum design decision (already agreed)

- **Parallel mode:** same units 9–18, `mode:figures` playlist alongside `mode:roman`
- **Taxonomy:** `analysis.figured_bass.cumulative` and `analysis.figured_bass.new` per unit, same schema as `analysis.roman`
- **Unit mapping (proposed):**
  - Unit 9: `5/3` → nothing, `6` (root position and first position triads)
  - Unit 10: adds `6/5`, `4/3` (first position sevenths — what Roman numerals call "first inversion sevenths")
  - Unit 11: adds `6/4` (the fourth-and-sixth sonority — Roman numerals call it "second inversion")  
  - Unit 12: adds `7`, `4/2`, `2` (root position and third position seventh chords)
  - Unit 13 (Rule of the Octave): the whole point — bass scale with standard figures at each degree
  - Units 14–18: chromatic figures (`b6`, `#4`, `#`, etc.)

**Open question for brainstorm:** Does the figured bass unit ordering match Roman numeral units 1:1, or does it have a different pedagogical sequence? (e.g. figured bass might introduce `6/4` before `6/5`/`4/3`)

## What needs to be designed (next brainstorm)

1. **Figured bass taxonomy schema** — `analysis.figured_bass` per unit, cumulative/new lists with `value` and `display` fields
2. **Python figured bass calculator** — port abbreviation rules to Python; store `raw_figured_bass` (complete) and `figured_bass` (abbreviated) — or just store complete and abbreviate at request time
3. **Import pipeline** — `_build_figured_bass_overrides()` in `import_bach_phrases.py`; runs alongside Roman numeral analysis
4. **Targeting layer** — figured bass targeting is simpler than Roman numerals (no secondary function disambiguation); a figure is in-scope if it's in `cumulative`
5. **JS rendering** — figured bass display uses stacked numbers (VexFlow or HTML overlay); `displayMap` handles Unicode (`⁶`, `⁴`, `#`, `♭`)
6. **Playlist command** — `create_unit_playlist --mode figures`

## Repository state

Branch: `docs/taxonomy-source-of-truth-viz`  
Recent commits: Roman numeral pipeline complete, all tests passing (30/30).  
Run `python manage.py runserver` to start. DB user: `avner-local2025@localhost`.
