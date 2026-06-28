# HarmonyLab Music Theory Canon

This file records human-authored music-theory rules for HarmonyLab. It is more
authoritative than stale implementation comments, generated docs, historical
plans, or agent assumptions.

Before modifying analysis, generation, grading, taxonomy analysis values, or
music21 boundary code, state the relevant rule from first principles and compare
the current code/docs against this canon. If there is a contradiction, surface it
to the product owner instead of silently treating existing behavior as project
convention.

## Interval quality

Interval quality is determined from two independent facts:

- the generic interval number, counted by note-letter distance;
- the chromatic size, counted by semitones.

Semitone count alone is insufficient. A six-semitone tritone may be either an
augmented fourth or a diminished fifth, depending on the generic interval.

In HarmonyLab figured-bass terminology:

| Lower note | Upper note | Generic interval | Semitones | Figure |
|---|---|---:|---:|---|
| F | B | 4th | 6 | `4+` |
| B | F | 5th | 6 | `5°` |

Do not normalize all tritones to augmented intervals. A diminished fifth above
the bass is `5°`, not `5+`.

## Figured bass

Figured bass labels intervals above the bass, not Roman numeral names or chord
inversion labels. First identify the sounding bass, then compute each upper
pitch's generic interval and chromatic alteration relative to the relevant key
or spelling context.

Common abbreviations may hide complete interval stacks, but they must not change
the underlying interval identities. For example, a complete first-inversion
triad with a third and sixth above the bass abbreviates to `6`; it is not
derived by first choosing a Roman numeral inversion.

### Figured bass: required vs allowed tones

A figure names the generic intervals *available* above the bass; it does **not** mean all of them
must sound. Which tones are *required* (must be present) vs merely *allowed* (legal but optional)
depends on the chord and the number of voices (Kellner 1732 / Remes realization rules).

- **allowed** = the bass plus every interval the figure names.
- **required** = the tones that survive in *every* valid realization across the exercise's voice
  range `[voiceCountPolicy.min .. max]`. The perfect 5th of a root-position triad (`5/3`) is the
  canonical omittable tone — at three voices you may double the root and drop the 5th, so the 5th
  is allowed but not required. An **altered** interval (`5°`, `b5`, `#6`, `4+`, …) is always
  required.

The authoritative realization table lives in code:
`apps/exercises/harmonization/figure_realization.py` (`TABLE`). It is the single source of truth;
`docs/FIGURED_BASS.md` mirrors it for humans. Changing a realization is a music-theory change —
follow the theory-sensitive-change rule in AGENTS.md and add a distinguishing golden case in
`theory_golden/figure_realization.json`. Figures that match no prototype fail safe (all named
tones required); run `python manage.py audit_figure_realization_coverage` to see which corpus
figures fall through (≈95% of harmonization targets map to a prototype; the remainder are
incomplete/altered voicings where all-required is harmless or correct).

## Agent review rule

For theory-sensitive changes, include or verify a distinguishing example. The
example should separate the correct rule from a plausible incorrect shortcut.
For interval-quality work, `F-B = 4+` and `B-F = 5°` are the minimum pair.
