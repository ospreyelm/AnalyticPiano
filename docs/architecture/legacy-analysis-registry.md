# Legacy Analysis Options Registry

This document serves as the official registry for legacy analysis options in HarmonyLab. It maps the user-facing checkboxes in the teacher/student interfaces to their exact database keys, configuration schemas, and underlying musical definitions.

---

## 1. Analysis Options Mapping

The options visible in the "ANALYZE" panel are divided into three columns:

| UI Label | Database/Code Key | Group / Column | Description |
|---|---|---|---|
| **Letters** | `note_names` | Column 1 (Pitch) | Letter names of pitches (e.g., "C", "F#", "Bb") |
| **Scientific pitch** | `scientific_pitch` | Column 1 (Pitch) | Note names with octaves (e.g., "C4", "F#3") |
| **Fixed-do** | `fixed_do` | Column 1 (Pitch) | Fixed-do solfege syllables (e.g., "do", "fa diesis") |
| **Pitch class** | `pitch_class` | Column 1 (Pitch) | Pitch class integers `0`–`11` (where C = 0) |
| **Degrees** | `scale_degrees` | Column 1 (Pitch) | Scale degree numbers relative to local key (e.g., `^1`, `^3`) |
| **Movable-do with LA- minor** | `solfege` | Column 1 (Pitch) | Movable-do solfege with minor key tonic mapped to "la" |
| **Movable-do with DO-minor** | `do_based_solfege` | Column 1 (Pitch) | Movable-do solfege with minor key tonic mapped to "do" |
| **Intervals** | `intervals` | Column 2 (Interval) | Specific intervals between adjacent voices |
| **Intervals (wrap after octave)** | `intervals_wrap_after_octave` | Column 2 (Interval) | Specific intervals compound-reduced to a single octave |
| **Intervals (wrap after octave plus ditone)** | `intervals_wrap_after_octave_plus_ditone` | Column 2 (Interval) | Specific intervals compound-reduced with 9th-inversion wrap |
| **Generic intervals** | `generic_intervals` | Column 2 (Interval) | Generic diatonic intervals (e.g., "3rd", "5th") |
| **Generic intervals (wrap after octave)** | `generic_intervals_wrap_after_octave` | Column 2 (Interval) | Generic intervals reduced to a single octave |
| **Generic intervals (wrap after octave plus ditone)** | `generic_intervals_wrap_after_octave_plus_ditone` | Column 2 (Interval) | Generic intervals compound-reduced with 9th-inversion wrap |
| **Pitch-class intervals** | `pci` | Column 2 (Interval) | Ordered pitch-class intervals (semitones `0`–`11`) |
| **Chord labels (E)** | `chord_labels` | Column 3 (Harmony) | Textual chord names/qualities (e.g., "C Major Triad") |
| **Harmony in Roman numerals** | `roman_numerals` | Column 3 (Harmony) | Roman numeral analysis in local key (e.g., "I", "IV6") |
| **Spacing of upper voices** | `spacing` | Column 3 (Harmony) | Spacing/distribution of SAT voices (e.g., "close", "open") |
| **Set class—set** | `set_class_set` | Column 3 (Harmony) | Pitch class set content (e.g., `"{C,E,G}"`) |
| **Set class—normal order** | `set_class_normal` | Column 3 (Harmony) | Pitch classes in normal order (e.g., `"[0, 4, 7]"`) |
| **Set class—prime form** | `set_class_prime` | Column 3 (Harmony) | Prime form of the pitch class set (e.g., `"<037>"`) |
| **Set class—Forte** | `set_class_forte` | Column 3 (Harmony) | Forte number classification (e.g., `"3-11"`) |
| **Figured bass (G)** | `thoroughbass` | Column 3 (Harmony) | Diatonic figured bass numerals (e.g., `"6"`, `"6/4"`) |
| **Abbreviate figured bass (V)** | `abbreviate_thoroughbass` | Column 3 (Harmony) | Flag to enable Kellner/Common-practice abbreviations for figures |

---

## 2. Configuration JSON Schema

In legacy play settings (`Exercise.data`), these settings are stored as boolean flags inside the `mode` sub-dictionary:

```json
{
  "mode": {
    "note_names": true,
    "scientific_pitch": false,
    "fixed_do": false,
    "pitch_class": false,
    "scale_degrees": false,
    "solfege": false,
    "do_based_solfege": false,
    "intervals": false,
    "intervals_wrap_after_octave": false,
    "intervals_wrap_after_octave_plus_ditone": false,
    "generic_intervals": false,
    "generic_intervals_wrap_after_octave": false,
    "generic_intervals_wrap_after_octave_plus_ditone": false,
    "pci": false,
    "chord_labels": true,
    "roman_numerals": true,
    "spacing": false,
    "set_class_set": false,
    "set_class_normal": false,
    "set_class_prime": false,
    "set_class_forte": false,
    "thoroughbass": false,
    "abbreviate_thoroughbass": false
  }
}
```
