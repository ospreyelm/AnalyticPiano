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

## Agent review rule

For theory-sensitive changes, include or verify a distinguishing example. The
example should separate the correct rule from a plausible incorrect shortcut.
For interval-quality work, `F-B = 4+` and `B-F = 5°` are the minimum pair.
