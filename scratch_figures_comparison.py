"""
Compare three approaches to deriving notes from figured bass:
  A) Our derive_required_notes() (figures.py, diatonic scale-walk)
  B) music21 FiguredBassNote realizer
  C) Original Bach chord pitch classes (ground truth)

Run from worktree root:
  DJANGO_SETTINGS_MODULE=harmony.settings.local python3 scratch_figures_comparison.py
"""
from __future__ import annotations
import json, sys, os, collections

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.local")
sys.path.insert(0, os.path.dirname(__file__))

import django; django.setup()

from music21 import chord as m21chord, key as m21key, pitch as m21pitch
from music21 import figuredBass as m21fb

from apps.exercises.utils.figured_bass import compute_figured_bass
from apps.exercises.harmonization.figures import derive_required_notes

CORPUS_PATH = "data/corpus/bach/bwv153.1.json"

_DUR_TICKS = {"w": 4096, "h": 2048, "q": 1024, "8": 512, "16": 256, "32": 128}
SEMITONES  = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def item_dur(item: dict) -> int:
    base = _DUR_TICKS.get(item["duration"]["type"], 1024)
    dots = item["duration"].get("dots", 0)
    add = base // 2
    for _ in range(dots):
        base += add; add //= 2
    return base


def pitch_to_midi(p: dict) -> int:
    return (p["octave"] + 1) * 12 + SEMITONES[p["step"]] + int(p.get("alter") or 0)


def pitch_name(p: dict) -> str:
    name = p["step"]
    alter = int(p.get("alter") or 0)
    if alter ==  1: name += "#"
    if alter == -1: name += "b"
    return name


def collect_onsets(score: dict) -> list[dict]:
    """
    Walk every voice in every measure, record (onset_tick → set of midi).
    Then for each onset group, lowest midi = bass.
    """
    onset_midis: dict[int, list[int]] = collections.defaultdict(list)
    onset_bass_pitch: dict[int, dict] = {}

    measure_tick = 0
    for measure in score["measures"]:
        for staff, sv in measure["staves"].items():
            for voice in sv["voices"]:
                t = measure_tick
                for item in voice["items"]:
                    dur = item_dur(item)
                    if item["kind"] == "note":
                        midi = pitch_to_midi(item["pitch"])
                        onset_midis[t].append(midi)
                    elif item["kind"] == "chord":
                        for h in item.get("heads", []):
                            onset_midis[t].append(pitch_to_midi(h))
                    t += dur

        # advance measure_tick by longest voice duration in this measure
        max_dur = 0
        for staff, sv in measure["staves"].items():
            for voice in sv["voices"]:
                vdur = sum(item_dur(i) for i in voice["items"])
                max_dur = max(max_dur, vdur)
        measure_tick += max_dur

    # Resolve bass pitch dict for each onset (need step/alter for key lookup)
    # Second pass: store lowest pitch object per onset
    bass_pitch_map: dict[int, dict] = {}
    measure_tick = 0
    for measure in score["measures"]:
        for staff, sv in measure["staves"].items():
            for voice in sv["voices"]:
                t = measure_tick
                for item in voice["items"]:
                    dur = item_dur(item)
                    if item["kind"] == "note":
                        midi = pitch_to_midi(item["pitch"])
                        cur = bass_pitch_map.get(t)
                        if cur is None or midi < cur[0]:
                            bass_pitch_map[t] = (midi, item["pitch"])
                    t += dur
        max_dur = 0
        for staff, sv in measure["staves"].items():
            for voice in sv["voices"]:
                vdur = sum(item_dur(i) for i in voice["items"])
                max_dur = max(max_dur, vdur)
        measure_tick += max_dur

    result = []
    for tick in sorted(onset_midis.keys()):
        midis = sorted(set(onset_midis[tick]))
        bass_info = bass_pitch_map.get(tick)
        if bass_info is None:
            continue
        bass_midi, bass_pitch = bass_info
        result.append({
            "tick": tick,
            "all_midis": midis,
            "bass_midi": bass_midi,
            "bass_pitch": bass_pitch,
        })
    return result


def m21_key_from_meta(meta: dict) -> m21key.Key:
    raw = meta.get("key", "C")
    # music21 Key accepts "Em", "a", "G" etc.
    return m21key.Key(raw)


def m21_realizer_pcs(key_obj: m21key.Key, bass_name: str, raw_fb: str) -> set[int]:
    from music21 import note as m21note
    try:
        fb_line = m21fb.realizer.FiguredBassLine(key_obj)
        fb_line.addElement(m21note.Note(bass_name + "3"), raw_fb or "")
        solutions = fb_line.realize()
        all_pcs: set[int] = set()
        for prog in solutions.getAllPossibilityProgressions()[:30]:
            for poss in prog:
                for p in poss:
                    all_pcs.add(p.pitchClass)
        return all_pcs
    except Exception as e:
        return {f"ERR:{e}"}


def main():
    cir   = json.load(open(CORPUS_PATH))
    score = cir["score"]
    meta  = score.get("meta", {})
    key_obj = m21_key_from_meta(meta)
    key_name = meta.get("key", "C")

    print(f"Corpus: {CORPUS_PATH}")
    print(f"Key: {key_name} → music21: {key_obj}\n")

    onsets = collect_onsets(score)
    print(f"{len(onsets)} onset slices total — comparing first 20\n")

    # Skip onsets with only one pitch (rests in upper voices, passing tones)
    chord_onsets = [o for o in onsets if len(o["all_midis"]) >= 3]

    rows = []
    for onset in chord_onsets[:20]:
        all_midis    = onset["all_midis"]
        bass_pitch   = onset["bass_pitch"]
        original_pcs = set(m % 12 for m in all_midis)

        m21c           = m21chord.Chord([m21pitch.Pitch(m) for m in all_midis])
        raw_fb, abbrev = compute_figured_bass(m21c, key_obj)
        bass_name      = pitch_name(bass_pitch)

        # A) ours
        try:
            derived  = derive_required_notes(key_name=key_name, bass_name=bass_name, figure=abbrev)
            our_pcs  = set(derived["allowed_pcs"])
            our_err  = None
        except Exception as e:
            our_pcs  = set()
            our_err  = str(e)

        # B) music21 realizer
        m21_pcs = m21_realizer_pcs(key_obj, bass_name, raw_fb)

        our_match = (original_pcs == our_pcs)
        m21_match = original_pcs.issubset(m21_pcs) if not any(str(x).startswith("ERR") for x in m21_pcs) else False

        rows.append({
            "tick":         onset["tick"],
            "bass":         bass_name,
            "raw_fb":       raw_fb,
            "abbrev":       abbrev,
            "original_pcs": sorted(original_pcs),
            "our_pcs":      sorted(our_pcs),
            "our_err":      our_err,
            "m21_pcs":      sorted(m21_pcs) if not any(str(x).startswith("ERR") for x in m21_pcs) else list(m21_pcs),
            "our_match":    our_match,
            "m21_match":    m21_match,
        })

    # --- terminal summary ---
    matches_ours = sum(1 for r in rows if r["our_match"])
    matches_m21  = sum(1 for r in rows if r["m21_match"])
    print(f"Our match:  {matches_ours}/{len(rows)}")
    print(f"m21 match:  {matches_m21}/{len(rows)}")
    print("\nMismatches (ours):")
    for r in rows:
        if not r["our_match"]:
            err = f"  ERR: {r['our_err']}" if r["our_err"] else ""
            print(f"  tick={r['tick']} bass={r['bass']} abbrev={r['abbrev']!r} "
                  f"orig={r['original_pcs']} ours={r['our_pcs']}{err}")

    # --- HTML ---
    def pstr(pcs): return ", ".join(str(x) for x in pcs)
    def bg(match): return "background:#d4edda" if match else "background:#f8d7da"

    trs = []
    for r in rows:
        err_note = f"<br><small style='color:red'>{r['our_err']}</small>" if r["our_err"] else ""
        trs.append(
            f"<tr>"
            f"<td>{r['tick']}</td>"
            f"<td><b>{r['bass']}</b></td>"
            f"<td><code>{r['raw_fb']}</code></td>"
            f"<td><code>{r['abbrev']}</code></td>"
            f"<td>{pstr(r['original_pcs'])}</td>"
            f"<td style='{bg(r['our_match'])}'>{pstr(r['our_pcs'])}{err_note}</td>"
            f"<td style='{bg(r['m21_match'])}'>{pstr(r['m21_pcs'])}</td>"
            f"</tr>"
        )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>FB Comparison — {CORPUS_PATH} ({key_name})</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:24px;color:#172033}}
  table{{border-collapse:collapse;width:100%;max-width:1200px;font-size:.85em}}
  th,td{{border:1px solid #d8dee9;padding:6px 9px;text-align:left;vertical-align:top}}
  th{{background:#f5f7fb}} code{{font-size:.95em}}
</style></head><body>
<h1>Figured Bass Comparison — {CORPUS_PATH}</h1>
<p>Key: <b>{key_name}</b> &nbsp;|&nbsp;
  <b>Original PCs</b>: Bach score &nbsp;|&nbsp;
  <b>Ours</b>: <code>derive_required_notes()</code> &nbsp;|&nbsp;
  <b>m21</b>: union of first 30 realizations from <code>FiguredBassLine</code>.
  Green = match, Red = mismatch.
</p>
<table>
<thead><tr><th>Tick</th><th>Bass</th><th>Raw FB</th><th>Abbrev</th>
<th>Original PCs</th><th>Ours</th><th>music21</th></tr></thead>
<tbody>{"".join(trs)}</tbody>
</table></body></html>"""

    out = "lab/static/harmonization-comparison.html"
    open(out, "w").write(html)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
