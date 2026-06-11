"""Key normalization helpers for backend music21 boundaries.

HarmonyLab stores tonal keys as pseudo keys like `jC_`, `jBb`, `iA_`, and
`iF#`. music21 expects conventional key names such as `C`, `Bb`, `A minor`,
and `F# minor`.
"""


def harmony_key_to_music21(value: str | None, *, default: str = "C") -> str:
    if not value:
        return default

    key_text = str(value).strip()
    if not key_text:
        return default

    if key_text.startswith(("j", "i")) and len(key_text) >= 2:
        mode_prefix = key_text[0]
        tonic = key_text[1:].replace("_", "")
        tonic = tonic.replace("-", "b")
        if not tonic:
            return default
        if mode_prefix == "i":
            return f"{tonic} minor"
        return tonic

    normalized = key_text.replace("-", "b")
    if normalized.endswith("m") and not normalized.endswith(" minor"):
        return f"{normalized[:-1]} minor"
    return normalized
