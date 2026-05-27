# HarmonyLab Exercise Type Schemas

JSON Schema (draft 2020-12) files, one per exercise type/mode combination.

| Schema file | type | mode | Grader | DB count |
|-------------|------|------|--------|----------|
| [umto_chorale_playback.schema.json](umto_chorale_playback.schema.json) | `umto_chorale` | `playback` | ChoraleGrader (exact pitch) | ~23k |
| [umto_chorale_identification.schema.json](umto_chorale_identification.schema.json) | `umto_chorale` | `identification` | IdentificationGrader | ~23k |
| [umto_chorale_analysis_match.schema.json](umto_chorale_analysis_match.schema.json) | `umto_chorale` | `analysis_match` | ChoraleGrader (pitch-class) | ~23k |
| [umto_chorale_harmonization.schema.json](umto_chorale_harmonization.schema.json) | `umto_chorale` | `harmonization` | HarmonizationGrader | ~23k |
| [umto_barline_placement.schema.json](umto_barline_placement.schema.json) | `umto_barline_placement` | `identification` | BarlineGrader | 26,490 |
| [umto_key_signature.schema.json](umto_key_signature.schema.json) | `umto_key_signature` | `identification` | IdentificationGrader | 12 |
| [umto_symbolic_meter.schema.json](umto_symbolic_meter.schema.json) | `umto_symbolic_meter` | `identification` | IdentificationGrader | 2 |
| [clausula_playback.schema.json](clausula_playback.schema.json) | `umto_chorale` | `playback` + `branch_b` tag | ChoraleGrader | varies |

Each schema includes:
- Required/optional field definitions with types and descriptions
- `examples[]` array containing a real DB example
- `x-*` extension fields for non-schema metadata (grading algorithms, generation commands, cross-references)

## Shared sub-types

The `umto_chorale_playback` schema defines `$defs` for `GradingSlice`, `VoiceEvent`, `AnalysisSlice`, `UMTOObject`, and `CIRMeasure` that all `umto_chorale` variants share. Other schemas inline or reference these as needed.

## Human-readable companion

[../exercise-types-reference.html](../exercise-types-reference.html) — dark-themed HTML reference with the same coverage, rendered with annotated JSON examples and explanatory prose.

## Identifying clausula exercises

Clausula exercises share `type: "umto_chorale"` and `mode: "playback"` with Branch A Bach-chorale exercises. Distinguish by `Exercise.skill_tags`:

```python
Exercise.objects.filter(skill_tags__contains=['branch_b'])          # all clausulae
Exercise.objects.filter(skill_tags__contains=['clausula_discant'])   # Discant type only
```
