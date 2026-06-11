# Music21 Key Normalization Audit Notes

Command:

```bash
rg -n 'key\.Key\(' apps/exercises -S
```

## Classification

- `apps/exercises/roman_derivation.py:60` - safe: `derive_cadence()` is used by Clausulae generation with clean tonal-center names such as `C`/`G`, not stored Exercise/UMTO/CIR pseudo-key tokens.
- `apps/exercises/generation/music21_builder.py:144` - safe: `_m21_key()` maps HarmonyLab generation keys through `KEY_MAP` before constructing `music21.key.Key`.
- `apps/exercises/harmonization/figures.py:172` - safe: `derive_required_notes()` normalizes display key names through `_normalize_key_name()` before constructing `music21.key.Key`.
- `apps/exercises/umto_factory.py:291` - safe: `_to_music21_key()` fallback for empty key text.
- `apps/exercises/umto_factory.py:295` - safe: `_to_music21_key()` converts stored HarmonyLab `j...` / `i...` keys into tonic/mode before constructing `music21.key.Key`.
- `apps/exercises/umto_factory.py:300` - safe: `_to_music21_key()` converts conventional `"<tonic> major|minor"` text into tonic/mode before constructing `music21.key.Key`.
- `apps/exercises/umto_factory.py:301` - safe: `_to_music21_key()` pass-through for already clean key names.
- `apps/exercises/utils/umto_import_router.py:132` - safe: `_harmony_key_to_tonic_mode()` converts stored HarmonyLab keys into tonic/mode before constructing `music21.key.Key`.
- `apps/exercises/utils/music21_builder.py:245` - safe: default clean fallback key object for scores without a key signature.
- `apps/exercises/management/commands/generate_unit1.py:99` - safe: receives clean corpus key names before conversion to HarmonyLab exercise key format.
- `apps/exercises/management/commands/audit_compendium_cadences.py:124` - safe: compendium examples provide separate clean tonic and mode fields.
- `apps/exercises/tests/test_compendium_source.py:35` - safe: test-only construction from clean compendium tonic/mode fixtures.
- `apps/exercises/utils/skills_analyzer.py:71` - safe: `_normalize_key_token()` converts stored HarmonyLab keys into tonic/mode before constructing `music21.key.Key`.
- `apps/exercises/utils/skills_analyzer.py:72` - safe: `_normalize_key_token()` pass-through for already clean conventional names.
- `apps/exercises/compendium_prep.py:396` - safe: compendium examples provide separate clean tonic and mode fields.
- `apps/exercises/tests/test_figured_bass.py:68` - safe: test-only construction from clean figured-bass test keys.
- `apps/exercises/tests/test_music21_builder.py:420` - safe: test-only clean key insertion.
- `apps/exercises/tests/test_music21_builder.py:446` - safe: test-only clean key insertion.
- `apps/exercises/management/commands/import_bach_phrases.py:76` - safe: converts When in Rome local key names into tonic/mode before constructing `music21.key.Key`.
- `apps/exercises/management/commands/import_bach_phrases.py:96` - safe: constructs a transposed music21 key from an existing music21 tonic object and mode.

## Patch Decision

No additional direct `music21.key.Key()` caller from this audit passed a stored Exercise/UMTO/CIR `j...` or `i...` string directly into music21 without an existing conversion step.
