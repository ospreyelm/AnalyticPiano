"""
Notation layer — converts Z₇ clausula triples to music21 objects.

key_realize(triple, key, octave) -> list[music21.note.Note]
score_cadence(voices, key)       -> music21.Score

'voices' for score_cadence is a list of dicts, each with:
  - 'triple': (ant, pen, ult) in Z₇
  - 'tau':    0 (early, τ=0) or 1 (late, τ=1)
  - 'pi':     Z₇ degree for the pickup note (only required when tau=1)
  - 'octave': starting octave for this voice (default: caller provides or use default)

Temporal grid for compound cadences (Section 2.3):

  Beat:  0       0.5     1       1.5     2
  Early: ANT             PEN             ULT
  Late:  (π=rest)        ANT     PEN     ULT

In 'authentic' mode the π position is a quarter rest, not a pitch.
All ULTs land together at beat 2. Notes placed by explicit offset so
voices always align correctly regardless of duration scheme.

Duration modes (score_cadence `duration` parameter):
  'authentic' — matches Compendium (Remeš): ANT=half, PEN=half, ULT=whole,
                2/2 time; compound late: rest=qtr, pi=qtr, ANT=qtr, PEN=qtr,
                ULT=whole (default)
  'whole'     — simple: 3 whole notes; compound: whole/half grid
  'quarter'   — simple: 3 quarter notes; compound: quarter/eighth grid
"""

from music21 import (
    clef,
    key as m21key,
    meter,
    note,
    pitch,
    scale,
    stream,
)

from .core import SOLFEGE


# ── Octave tracking ───────────────────────────────────────────────────────────

def _next_octave(prev_z7, next_z7, prev_octave, sc):
    """
    Given a move from prev_z7 to next_z7 in Z₇, choose the nearest octave
    for next_z7 — preferring the smaller diatonic interval (up or down).
    Ascending interval ≤ 3 steps: go up. ≥ 4 steps: go down (closer).

    Uses actual chromatic MIDI values (not raw Z₇ indices) to detect whether
    an octave boundary is crossed.  This is necessary because music21 octave
    numbers reset at C, so in non-C keys the leading-tone Ti sits BELOW Do
    within the same octave number (e.g. F#5 < G5) and must NOT be dropped
    an octave.
    """
    asc = (next_z7 - prev_z7) % 7
    prev_p = pitch.Pitch(sc.pitchFromDegree(prev_z7 + 1).name)
    prev_p.octave = prev_octave
    next_p = pitch.Pitch(sc.pitchFromDegree(next_z7 + 1).name)
    next_p.octave = prev_octave
    if asc <= 3:
        # ascending motion: want next pitch ≥ prev pitch
        return prev_octave if next_p.midi >= prev_p.midi else prev_octave + 1
    else:
        # descending motion: want next pitch ≤ prev pitch
        return prev_octave if next_p.midi <= prev_p.midi else prev_octave - 1


def _z7_to_note(z7_degree, sc, octave, quarter_length=1.0, labels=()):
    """
    Convert a Z₇ degree to a music21 Note at the given octave.
    labels: sequence of strings added as stacked lyrics (line 1, 2, …).
    """
    m21_degree = z7_degree + 1          # Z₇ 0-6 → music21 scale degree 1-7
    p = sc.pitchFromDegree(m21_degree)
    p = pitch.Pitch(p.name)             # strip default octave
    p.octave = octave
    n = note.Note(p, quarterLength=quarter_length)
    for i, text in enumerate(labels, start=1):
        n.addLyric(text, lyricNumber=i)
    return n


# ── Public API ────────────────────────────────────────────────────────────────

def key_realize(triple, key, octave=4):
    """
    Convert a Z₇ clausula triple to a list of three music21 Notes.

    Parameters
    ----------
    triple : (int, int, int)
        (ANT, PEN, ULT) scale degrees in Z₇ (0=Do … 6=Ti).
    key : str
        Key center as a music21 pitch name: 'C', 'G', 'Bb', 'F#', etc.
        Assumes major mode. Pass 'B-' for B-flat (music21 convention).
    octave : int
        Octave of the ANT note (default 4). Subsequent notes track the
        nearest diatonic step up or down.

    Returns
    -------
    list[music21.note.Note]
        Three notes: [ANT, PEN, ULT], each with duration quarterLength=1.
    """
    sc = scale.MajorScale(key)
    a, p, u = triple
    oct_a = octave
    oct_p = _next_octave(a, p, oct_a, sc)
    oct_u = _next_octave(p, u, oct_p, sc)
    return [
        _z7_to_note(a, sc, oct_a),
        _z7_to_note(p, sc, oct_p),
        _z7_to_note(u, sc, oct_u),
    ]


def pitch_to_z7(pitch_name: str, key: str, mode: str = "major"):
    """
    Convert a pitch name to a Z₇ scale degree given a key and mode.

    Parameters
    ----------
    pitch_name : str
        music21 pitch string, e.g. 'C4', 'G#4', 'B-3'.
    key : str
        Key center as a music21 pitch name: 'C', 'A', 'F#', etc.
    mode : str
        'major' (default) or 'minor' (natural minor = diatonic set).

    Returns
    -------
    (z7_degree, accidental) where:
        z7_degree  : int 0–6 (Do=0 … Ti=6), always the diatonic degree
        accidental : None if diatonic; 'sharp', 'flat', 'double-sharp', etc.
                     if chromatically inflected. In minor keys, the raised
                     leading tone returns (6, 'sharp') — Ti with musica ficta.

    Raises
    ------
    ValueError if the pitch cannot be resolved against the scale.
    """
    if mode == "minor":
        sc = scale.MinorScale(key)
    else:
        sc = scale.MajorScale(key)
    try:
        p = pitch.Pitch(pitch_name)
    except Exception as exc:
        raise ValueError(f"Invalid pitch name {pitch_name!r}: {exc}") from exc
    scale_degree, acc = sc.getScaleDegreeAndAccidentalFromPitch(p)
    if scale_degree is None:
        raise ValueError(f"Cannot resolve pitch {pitch_name!r} in {key} {mode}")
    z7_degree = (scale_degree - 1) % 7
    acc_str = str(acc) if acc is not None else None
    return z7_degree, acc_str


# ── Score builder ─────────────────────────────────────────────────────────────

_BASS_CLEF_VOICES  = {"Bass"}
_TREBLE_CLEF_VOICES = {"Discant", "Alto", "Tenor"}

# Default octaves by voice type for a comfortable range
_DEFAULT_OCTAVE = {"Discant": 5, "Alto": 4, "Tenor": 4, "Bass": 3}


def score_cadence(voices, key, labels=True, duration='authentic'):
    """
    Build a music21 Score from a list of voiced clausulae.

    Parameters
    ----------
    voices : list of dict
        Each dict must have:
          'triple'     : (ant, pen, ult) in Z₇
          'tau'        : 0 (early) or 1 (late)
          'name'       : clausula type string — 'Discant', 'Tenor', 'Alto', 'Bass'
          'octave'     : int, starting octave for this voice
        If tau=1 and duration is 'whole' or 'quarter', also include:
          'pi'         : int, Z₇ degree for the π pickup note
        In 'authentic' mode the π position is a rest — 'pi' is ignored.
    key : str
        Key center for music21 (e.g. 'C', 'G', 'B-'). Major mode assumed.
    labels : bool
        If True (default), add solfège (Do/Re/…) and position (ANT/PEN/ULT)
        as stacked lyrics. The π pickup note is labelled 'π'.
    duration : str
        'authentic' — matches Compendium (Remeš): ANT=half, PEN=half, ULT=whole,
                      2/2 time. Compound late: rest=qtr pi=qtr ANT=qtr PEN=qtr
                      ULT=whole. Both voices are 8 QL / 2 measures. (default)
        'whole'     — simple: 3 whole notes; compound: whole/half grid
        'quarter'   — simple: 3 quarter notes; compound: quarter/eighth grid

    Returns
    -------
    music21.stream.Score
        Each voice on its own Part/staff. Notes placed by explicit offset so
        all ULTs land together. Valid MusicXML: score.write('musicxml', fp=…)
    """
    # Duration scheme dict:
    #   time_sig — time signature string
    #   ant_dur  — quarter_length of ANT in early/simple voice
    #   pen_dur  — quarter_length of PEN in early/simple voice
    #   ult_e    — quarter_length of ULT in early voice
    #   ult_off  — offset of ULT in both voices (must be equal for alignment)
    #   use_pi   — whether to insert a π pickup note in late voice
    #              True:  rest(rest_l) + pi_note(pi_l) + ANT(ant_l) + PEN(pen_l) + ULT
    #              False: rest(rest_l) + ANT(ant_l) + PEN(pen_l) + ULT
    #   rest_l, pi_l, ant_l, pen_l, ult_l — late-voice durations
    #
    # 'authentic' matches Remeš Compendium (image 2):
    #   Early: half + half + whole  (2+2+4=8 QL, 2 measures of 2/2)
    #   Late:  qtr-rest + half-ANT + qtr-PEN + whole-ULT  (1+2+1+4=8 QL)
    #   No π note — the quarter rest IS the π position.
    _DURATION_SCHEMES = {
        # key:        time   ant  pen  ult_e ult_off use_pi rest pi   ant_l pen_l ult_l
        'authentic': ('2/2', 2.0, 2.0, 4.0,  4.0,  False, 1.0, None, 2.0,  1.0,  4.0),
        'whole':     ('3/1', 4.0, 4.0, 4.0,  8.0,  True,  2.0, 2.0,  4.0,  2.0,  4.0),
        'quarter':   ('3/4', 1.0, 1.0, 1.0,  2.0,  True,  0.5, 0.5,  1.0,  0.5,  1.0),
    }
    if duration not in _DURATION_SCHEMES:
        raise ValueError(f"duration must be 'authentic', 'whole', or 'quarter', got {duration!r}")
    (time_sig_str, ant_dur, pen_dur, ult_e_dur, ult_off,
     use_pi, rest_dur, pi_dur, ant_l_dur, pen_l_dur, ult_l_dur) = _DURATION_SCHEMES[duration]

    sc = scale.MajorScale(key)
    m21_key = m21key.Key(key)
    score = stream.Score()

    for v in voices:
        triple = v['triple']
        tau    = v['tau']
        name   = v.get('name', '')
        octave = v.get('octave', _DEFAULT_OCTAVE.get(name, 4))

        variant_idx = v.get('variant_idx')
        if variant_idx is not None:
            from .core import CLAUSULAE
            n_variants = len(CLAUSULAE.get(name, []))
            part_label = f"{name} (var. {variant_idx + 1})" if n_variants > 1 else name
        else:
            part_label = name

        part = stream.Part()
        part.partName = part_label
        part.id = part_label

        part.insert(0, meter.TimeSignature(time_sig_str))
        part.insert(0, m21_key)

        if name in _BASS_CLEF_VOICES:
            part.insert(0, clef.BassClef())
        else:
            part.insert(0, clef.TrebleClef())

        a, p, u = triple
        oct_a = octave
        oct_p = _next_octave(a, p, oct_a, sc)
        oct_u = _next_octave(p, u, oct_p, sc)

        def lbl(solfege_deg, position):
            if not labels:
                return ()
            return (SOLFEGE[solfege_deg], position)

        if tau == 0:
            # Early/simple voice: ANT at 0, PEN at ant_dur, ULT at ult_off
            part.insert(0,        _z7_to_note(a, sc, oct_a, quarter_length=ant_dur,   labels=lbl(a, "ANT")))
            part.insert(ant_dur,  _z7_to_note(p, sc, oct_p, quarter_length=pen_dur,   labels=lbl(p, "PEN")))
            part.insert(ult_off,  _z7_to_note(u, sc, oct_u, quarter_length=ult_e_dur, labels=lbl(u, "ULT")))

        else:
            # Late voice (tau=1) — Section 2.3 interleaved grid.
            # 'authentic': rest(qtr) + ANT(half) + PEN(qtr) + ULT(whole)
            # other modes: rest + π note + ANT + PEN + ULT
            ant_l_off = rest_dur + (pi_dur if use_pi else 0)

            r = note.Rest(quarterLength=rest_dur)
            if labels and not use_pi:
                r.addLyric("π", lyricNumber=1)
            part.insert(0, r)

            if use_pi:
                pi_deg = v['pi']
                oct_pi = _next_octave(a, pi_deg, oct_a, sc)
                pi_labels = (SOLFEGE[pi_deg], "π") if labels else ()
                part.insert(rest_dur, _z7_to_note(pi_deg, sc, oct_pi, quarter_length=pi_dur, labels=pi_labels))

            part.insert(ant_l_off,           _z7_to_note(a, sc, oct_a, quarter_length=ant_l_dur, labels=lbl(a, "ANT")))
            part.insert(ult_off - pen_l_dur, _z7_to_note(p, sc, oct_p, quarter_length=pen_l_dur, labels=lbl(p, "PEN")))
            part.insert(ult_off,             _z7_to_note(u, sc, oct_u, quarter_length=ult_l_dur, labels=lbl(u, "ULT")))

        score.append(part)

    return score
