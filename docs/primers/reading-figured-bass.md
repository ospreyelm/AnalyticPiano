# Reading Figured Bass — A Student Primer

Figured bass is shorthand. Under a bass note you see numbers; they tell you which **intervals to
build above that bass**. You read the bass from the staff and add the rest yourself.

## The numbers are steps above the bass

Count generic steps, starting from the bass as **1**:

- `1` = the bass itself (or its octave)
- `3` = a third above (two staff steps up)
- `5` = a fifth above (four steps up)
- `6` = a sixth above (five steps up)
- `7` = a seventh above
- `8` = the octave (the bass again, higher)

So `5/3` over a C means: play C (bass), the third above (E), and the fifth above (G) — a C triad.
Key-signature accidentals apply automatically; a `#`, `b`, or `n` next to a number changes that one
interval (a sharp or flat with no number always alters the **third**).

## Abbreviations

Composers leave out the obvious numbers. A plain bass note (no figure) means `5/3`. A `6` is short
for `6/3`. A `7` is short for `7/5/3`. The full list of abbreviations is standard (Kellner, 1732);
you'll learn the common ones by sight.

## You don't have to play every note

This is the part students miss: **the figure lists what's available, not everything you must play.**
How many notes you actually sound depends on how many voices you're writing.

- In **four voices**, a `5/3` triad is bass + 3rd + 5th + a doubled note (usually the bass).
- In **three voices**, you can drop the **5th** and double the root: bass + 3rd + bass again.
  The 5th of a plain triad is *optional*.
- The **third** is almost never omitted — it gives the chord its quality (major / minor).
- **Dissonances and altered tones** (a seventh, a suspended fourth, a sharped or flatted interval)
  are *required* — they're the whole point of the figure.

A quick rule of thumb: keep the 3rd and any dissonance or accidental; the perfect 5th is the first
thing you may drop.

## Worked examples

| Figure | Bass | Build | Must include | May drop |
|---|---|---|---|---|
| `5/3` | C | C E G | 3rd (E) | 5th (G) |
| `6` (`6/3`) | E | E G C | 3rd (G) and 6th (C) | — |
| `7` (`7/5/3`) | G | G B D F | 3rd (B) and 7th (F) | 5th (D) |
| `4/2` | D | D (bass) + … | the 2nd and 4th | the 6th, at three voices |

## Why grading accepts the omission

When you submit a chord, the app checks two things: every note you play must be **allowed** by the
figure, and every **required** tone must be present. Because the 5th of a triad is allowed but not
required, doubling the bass and dropping the 5th is graded correct — exactly as a real continuo
player would do it.

---

*Reference for maintainers: the required-vs-allowed rules are encoded in
`apps/exercises/harmonization/figure_realization.py` and documented in `docs/FIGURED_BASS.md`.*
