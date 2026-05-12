# scripts/convert_wir_corpus.py
"""One-time script: parse When in Rome Bach chorales into JSON.

Usage:
    python scripts/convert_wir_corpus.py /path/to/When-in-Rome/Corpus/Bach_Chorales/

Writes:
    data/when_in_rome/chorales.json
    data/when_in_rome/bwv_to_riemenschneider.json
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path


def parse_wir_file(text: str, riemenschneider: int) -> dict:
    """Parse a single WiR RomanText file into a structured dict.

    Returns:
        {
            "riemenschneider": int,
            "bwv": str | None,
            "title": str | None,
            "time_signature": str | None,
            "labels": [{"measure": int, "beat": float, "label": str, "local_key": str, "variant"?: str}]
        }
    """
    bwv = None
    title = None
    time_signature = None
    local_key = "?"
    labels: list[dict] = []

    HEADER_RE = re.compile(
        r'^(Note|Composer|BWV|Title|Analyst|Proofreader|Time Signature|Form):'
    )
    MEASURE_RE = re.compile(r'^m(\d+)(var\d+)?\s+(.*)')
    BEAT_RE = re.compile(r'^b(\d+(?:\.\d+)?)$')
    KEY_RE = re.compile(r'^[A-Ga-g][#b-]?:$')

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Extract specific header values
        if line.startswith('BWV:'):
            bwv = line[4:].strip()
            continue
        if line.startswith('Title:'):
            title = line[6:].strip()
            continue
        if line.startswith('Time Signature:'):
            time_signature = line[15:].strip()
            continue
        if HEADER_RE.match(line):
            continue

        m = MEASURE_RE.match(line)
        if not m:
            continue

        measure_num = int(m.group(1))
        is_var = bool(m.group(2))
        rest = m.group(3).strip()

        cur_beat = 1.0
        for token in rest.split():
            if not token:
                continue
            # Beat marker: b followed immediately by digit(s)
            beat_m = BEAT_RE.match(token)
            if beat_m:
                cur_beat = float(beat_m.group(1))
                continue
            # Repeat barline
            if token in ('||', ':||', '|'):
                continue
            # Key-change token: letter A-G or a-g + optional accidental + colon
            if KEY_RE.match(token):
                local_key = token[:-1]  # strip trailing ':'
                continue
            # RN label
            if is_var:
                # Find existing main label at this position to attach variant
                existing = next(
                    (l for l in labels
                     if l["measure"] == measure_num
                     and abs(l["beat"] - cur_beat) < 1e-6
                     and "variant" not in l),
                    None
                )
                if existing:
                    existing["variant"] = token
                else:
                    labels.append({
                        "measure": measure_num,
                        "beat": cur_beat,
                        "label": None,
                        "local_key": local_key,
                        "variant": token,
                    })
            else:
                labels.append({
                    "measure": measure_num,
                    "beat": cur_beat,
                    "label": token,
                    "local_key": local_key,
                })

    # Sort by (measure, beat)
    labels.sort(key=lambda l: (l["measure"], l["beat"]))

    return {
        "riemenschneider": riemenschneider,
        "bwv": bwv,
        "title": title,
        "time_signature": time_signature,
        "labels": labels,
    }


def main(wir_dir: str) -> None:
    wir_path = Path(wir_dir)
    if not wir_path.exists():
        print(f"ERROR: {wir_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Find all .txt files named NNN.txt (Riemenschneider numbers)
    txt_files = sorted(wir_path.glob("*.txt"))
    if not txt_files:
        print(f"ERROR: No .txt files found in {wir_dir}", file=sys.stderr)
        sys.exit(1)

    chorales: dict[str, dict] = {}
    bwv_map: dict[str, int] = {}
    errors = []

    for path in txt_files:
        # Filename should be NNN.txt
        stem = path.stem
        if not stem.isdigit():
            continue
        riem_num = int(stem)
        text = path.read_text(encoding='utf-8')
        try:
            result = parse_wir_file(text, riem_num)
        except Exception as e:
            errors.append(f"R{riem_num}: {e}")
            continue

        chorales[str(riem_num)] = result
        if result["bwv"]:
            bwv_map[result["bwv"]] = riem_num

    print(f"Parsed {len(chorales)} chorales, {len(errors)} errors")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)

    # Validate
    assert len(chorales) == 371, f"Expected 371 chorales, got {len(chorales)}"
    assert len(set(chorales.keys())) == len(chorales), "Duplicate Riemenschneider keys"

    out_dir = Path(__file__).parent.parent / "data" / "when_in_rome"
    out_dir.mkdir(parents=True, exist_ok=True)

    chorales_path = out_dir / "chorales.json"
    chorales_path.write_text(json.dumps(chorales, indent=2, ensure_ascii=False))
    print(f"Wrote {chorales_path}")

    bwv_path = out_dir / "bwv_to_riemenschneider.json"
    bwv_path.write_text(json.dumps(bwv_map, indent=2))
    print(f"Wrote {bwv_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} /path/to/When-in-Rome/Corpus/Bach_Chorales/")
        sys.exit(1)
    main(sys.argv[1])
