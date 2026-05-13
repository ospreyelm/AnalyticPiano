# When in Rome — Bach Chorales Corpus

This directory contains derived data from the When in Rome corpus.

## Source

- **Repository:** https://github.com/MarkGotham/When-in-Rome
- **Commit SHA:** aa7539f1 (Merge pull request #103 from measure-map/tavern_beethoven_woo63)
- **Subset:** `Corpus/Early_Choral/Bach,_Johann_Sebastian/Chorales/` (371 chorales)
- **Converted:** 2026-05-13

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

## Notes

- Analysts: Andrew Jones; proofreaders: Dmitri Tymoczko and Hamish Robb
- `local_key` is a running state tracked across each file: starts as `"?"` until the
  first key-change token (e.g. `G:`) appears, then updates on each subsequent key token.
- NCT beats (no WiR label) are identified by absence of an entry at that `(measure, beat)`.
- Variant readings (e.g. `m11var1`) are stored as `"variant"` field on label objects.
