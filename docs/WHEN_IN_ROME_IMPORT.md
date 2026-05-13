# When in Rome Bach Import

HarmonyLab uses the derived When in Rome (WiR) Bach chorale corpus for human-authored Roman numeral labels in Bach phrase imports. The import still keeps music21 output for auditing and figured-bass computation.

## Data Source

Derived WiR data lives in:

- `data/when_in_rome/chorales.json` — 371 standalone chorales keyed by Riemenschneider number.
- `data/when_in_rome/bwv_to_riemenschneider.json` — BWV-to-Riemenschneider lookup for mapped chorales.
- `apps/exercises/utils/wir_corpus.py` — runtime lookup helpers.

## Import Modes

`import_bach_phrases` supports:

| Mode | UMTO mode | Stored analysis |
|---|---|---|
| `roman` | `identification` | WiR Roman labels + local keys + music21 raw RN + figured bass |
| `matching` | `analysis_match` | Same WiR-backed analysis as `roman` |
| `play` | `playback` | Same WiR-backed analysis, available for overlays/debugging |
| `play_figures` | `playback` | Same WiR-backed analysis, with figured-bass display defaults |
| `figures` | `identification` | Computed abbreviated figured bass |
| `figures_unabbreviated` | `identification` | Computed raw figured-bass stacks |

WiR-backed modes hard-fail if the requested chorale is not in the WiR corpus. Existing imports can be refreshed with `--overwrite`.

## NCT Handling

The importer emits an analysis slice for every music21 chordify beat so analysis offsets stay aligned with score windows. If WiR has no label for a beat, the slice is retained with display fields set to `null`. The frontend hides these null-content slices while keeping positional alignment intact.

## Figured Bass Reconciliation

For WiR-backed modes, `roman_numeral` remains the canonical WiR label. Figured bass is computed separately and stored alongside it:

- `raw_roman_numeral` — music21 Roman numeral, for audit/debugging.
- `raw_figured_bass` — raw stack, such as `8/7/4`.
- `figured_bass` — pedagogically abbreviated figure, such as `7/4-3`.

The importer currently recognizes the `8/7/4 -> 8/7/3` suspension-resolution pattern and stores the first slice as `7/4-3`.

## Playlist Generation

Use `create_unit_playlist` for end-to-end import and playlist assembly:

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-30 \
  --author admin@example.com \
  --mode roman \
  --public
```

To refresh existing exercises after importer changes:

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-30 \
  --author admin@example.com \
  --mode roman \
  --overwrite
```

For playback exercises with figured-bass overlays:

```bash
python manage.py create_unit_playlist \
  --unit 9 \
  --riemenschneider 1-30 \
  --author admin@example.com \
  --mode play_figures
```

The Django admin and local content-generation UI expose the same mode choices and include an "Overwrite existing exercises" checkbox.
