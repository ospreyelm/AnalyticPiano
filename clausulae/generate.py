"""
Enumerate valid simple and compound clausula cadences.
"""

from itertools import product

from .core import ALL_CLAUSULAE, CLAUSULAE, MOD
from .constraints import (
    bass_constraint_ok,
    consonant_vertical,
    distinctness_ok,
    has_parallel_perfects,
    parallel_perfect,
    validate_simple,
)


def enumerate_simple(n_voices=2, require_discant=False, require_bass=False):
    """
    Enumerate all valid simple cadences of n_voices voices.
    Voice 0 is the lowest. Returns list of valid voice combinations.
    """
    valid = []
    for combo in product(ALL_CLAUSULAE, repeat=n_voices):
        names = [c[0] for c in combo]
        if require_discant and "Discant" not in names:
            continue
        if require_bass and "Bass" not in names:
            continue
        ok, _ = validate_simple(list(combo))
        if ok:
            valid.append(combo)
    return valid


def enumerate_compound(require_discant=True):
    """
    Enumerate valid compound two-voice cadences.

    Temporal grid (delay = half a beat):

      Beat:  0       0.5     1       1.5     2
      Early: ANT             PEN             ULT
      Late:          pi      ANT             ULT
                                     PEN

    Checks:
      1. pi consonant with early ANT          (beat 0.5 against beat 0)
      2. Both ULTs arrive together at beat 2  (consonant)
      3. No parallel perfects into the final  (early PEN→ULT vs late PEN→ULT)

    Suspension dissonance at beat 1 and late PEN at 1.5 are intrinsic to the
    clausula definitions — not validated here.

    Returns list of (c_early, c_late, valid_pi_list).
    """
    valid = []
    for c_early, c_late in product(ALL_CLAUSULAE, repeat=2):
        if c_early[2] == c_late[2]:
            continue

        if require_discant:
            if "Discant" not in (c_early[0], c_late[0]):
                continue

        early_ant, early_pen, early_ult = c_early[2]
        late_ant,  late_pen,  late_ult  = c_late[2]

        valid_pi = [pi for pi in range(MOD) if consonant_vertical([early_ant, pi])]

        if not consonant_vertical([early_ult, late_ult]):
            continue

        if parallel_perfect(
            (early_pen, early_ult, early_ult),
            (late_pen,  late_ult,  late_ult),
            0, 1
        ):
            continue

        if valid_pi:
            valid.append((c_early, c_late, valid_pi))

    return valid


def enumerate_compound_3voice_double_tau1(require_bass=True):
    """
    Enumerate valid 3-voice compound cadences where both upper voices are τ=1:
      voice 0 — Bass (τ=0)
      voice 1 — upper voice A (τ=1)
      voice 2 — upper voice B (τ=1)

    Temporal grid:
      Beat:  0      0.5    1      1.5    2
      Bass:  ANT           PEN           ULT    (τ=0)
      VoiceA: (rest)        ANT    PEN    ULT    (τ=1)
      VoiceB: (rest)        ANT    PEN    ULT    (τ=1)

    Checks:
      1. Pairwise ULT consonance: Bass+A, Bass+B, A+B
      2. Pairwise ANT consonance at beat 1: Bass-ANT(beat 0)+A-ANT, Bass+B-ANT, A+B
      3. No parallel perfects: each of the 3 pairs at PEN→ULT
      4. Distinctness across all three triples

    Returns list of (c_bass, c_upper_a, c_upper_b).
    """
    bass_clausulae = [c for c in ALL_CLAUSULAE if c[0] == "Bass"]
    upper_clausulae = [c for c in ALL_CLAUSULAE if c[0] != "Bass"]

    valid = []
    for c_bass in bass_clausulae:
        for c_a, c_b in product(upper_clausulae, repeat=2):
            if c_a[2] == c_b[2]:
                continue
            if not distinctness_ok([c_bass[2], c_a[2], c_b[2]]):
                continue

            bass_ant, bass_pen, bass_ult = c_bass[2]
            ant_a, pen_a, ult_a = c_a[2]
            ant_b, pen_b, ult_b = c_b[2]

            # ULT consonance (pairwise)
            if not consonant_vertical([bass_ult, ult_a]):
                continue
            if not consonant_vertical([bass_ult, ult_b]):
                continue
            if not consonant_vertical([ult_a, ult_b]):
                continue

            # ANT consonance at beat 1 (τ=1 ANTs against bass ANT at beat 0)
            if not consonant_vertical([bass_ant, ant_a]):
                continue
            if not consonant_vertical([bass_ant, ant_b]):
                continue
            if not consonant_vertical([ant_a, ant_b]):
                continue

            # No parallel perfects (all three pairs)
            if parallel_perfect((bass_pen, bass_ult, bass_ult), (pen_a, ult_a, ult_a), 0, 1):
                continue
            if parallel_perfect((bass_pen, bass_ult, bass_ult), (pen_b, ult_b, ult_b), 0, 1):
                continue
            if parallel_perfect((pen_a, ult_a, ult_a), (pen_b, ult_b, ult_b), 0, 1):
                continue

            valid.append((c_bass, c_a, c_b))

    return valid


def enumerate_compound_4voice(require_discant=True, require_bass=True):
    """
    Enumerate valid 4-voice compound cadences:
      voice 0 — Bass (τ=0)
      voices 1,2 — upper τ=0 voices (Tenor, Alto, or any non-Bass clausula)
      voice 3 — Discant (τ=1)

    Checks:
      1. Bass + each τ=0 upper form valid simple 2-voice cadences
      2. All three τ=0 voices (Bass + 2 uppers) + Discant τ=1 satisfy compound rules
         (ULT consonance, no parallel perfects) for each pairing with Discant
      3. Four-way ULT consonance
      4. No parallel perfects among all pairs at PEN→ULT
      5. Distinctness across all four triples

    Returns list of (c_bass, c_upper1, c_upper2, c_late).
    """
    bass_clausulae  = [c for c in ALL_CLAUSULAE if c[0] == "Bass"]
    upper_clausulae = [c for c in ALL_CLAUSULAE if c[0] not in ("Bass", "Discant")]
    late_clausulae  = [c for c in ALL_CLAUSULAE if c[0] == "Discant"]
    if not require_discant:
        late_clausulae = [c for c in ALL_CLAUSULAE if c[0] != "Bass"]

    valid = []
    for c_bass in bass_clausulae:
        for c_u1, c_u2 in product(upper_clausulae, repeat=2):
            if c_u1[2] == c_u2[2]:
                continue
            for c_late in late_clausulae:
                if not distinctness_ok([c_bass[2], c_u1[2], c_u2[2], c_late[2]]):
                    continue

                bass_ant, bass_pen, bass_ult   = c_bass[2]
                u1_ant,   u1_pen,   u1_ult     = c_u1[2]
                u2_ant,   u2_pen,   u2_ult     = c_u2[2]
                late_ant, late_pen, late_ult   = c_late[2]

                # Bass + u1 simple valid
                ok1, _ = validate_simple([c_bass, c_u1])
                if not ok1:
                    continue
                # Bass + u2 simple valid
                ok2, _ = validate_simple([c_bass, c_u2])
                if not ok2:
                    continue

                # Four-way ULT consonance
                if not consonant_vertical([bass_ult, u1_ult, u2_ult, late_ult]):
                    continue

                # No parallel perfects: all pairs at PEN→ULT
                pairs = [
                    ((bass_pen, bass_ult), (u1_pen, u1_ult)),
                    ((bass_pen, bass_ult), (u2_pen, u2_ult)),
                    ((bass_pen, bass_ult), (late_pen, late_ult)),
                    ((u1_pen, u1_ult),     (u2_pen, u2_ult)),
                    ((u1_pen, u1_ult),     (late_pen, late_ult)),
                    ((u2_pen, u2_ult),     (late_pen, late_ult)),
                ]
                has_pp = any(
                    parallel_perfect(
                        (pa, ua, ua), (pb, ub, ub), 0, 1
                    )
                    for (pa, ua), (pb, ub) in pairs
                )
                if has_pp:
                    continue

                valid.append((c_bass, c_u1, c_u2, c_late))

    return valid


def enumerate_compound_3voice(require_discant=True, require_bass=True):
    """
    Enumerate valid 3-voice compound cadences:
      voice 0 — Bass (τ=0, lowest)
      voice 1 — early upper voice (τ=0)
      voice 2 — late upper voice (τ=1)

    Temporal grid:
      Beat:  0      0.5    1      1.5    2
      Bass:  ANT           PEN           ULT    (τ=0)
      Early: ANT           PEN           ULT    (τ=0)
      Late:  (π=rest)      ANT    PEN    ULT    (τ=1)

    Checks (in addition to the 2-voice compound checks on early+late):
      1. Bass + early-upper form a valid simple 2-voice cadence
         (distinctness, no parallel perfects, vertical consonance at ANT/PEN/ULT)
      2. Three-way vertical consonance at ULT (beat 2): Bass + early + late all consonant
      3. No parallel perfects: Bass→early PEN→ULT and Bass→late PEN→ULT

    The suspension dissonance at beat 1 (late ANT against Bass/early PEN) is
    intrinsic to the clausula structure — not checked here.

    Returns list of (c_bass, c_early, c_late, valid_pi_list).
    """
    valid = []

    bass_clausulae  = [c for c in ALL_CLAUSULAE if c[0] == "Bass"]
    upper_clausulae = [c for c in ALL_CLAUSULAE if c[0] != "Bass"]

    for c_bass in bass_clausulae:
        for c_early, c_late in product(upper_clausulae, repeat=2):

            if require_discant and "Discant" not in (c_early[0], c_late[0]):
                continue

            # Distinctness across all three
            if not distinctness_ok([c_bass[2], c_early[2], c_late[2]]):
                continue

            bass_ant,  bass_pen,  bass_ult  = c_bass[2]
            early_ant, early_pen, early_ult = c_early[2]
            late_ant,  late_pen,  late_ult  = c_late[2]

            # 1. Bass + early must form a valid simple 2-voice cadence
            ok, _ = validate_simple([c_bass, c_early])
            if not ok:
                continue

            # 2. Compound checks on early + late (same as enumerate_compound)
            # ULT consonance: early + late
            if not consonant_vertical([early_ult, late_ult]):
                continue

            # No parallel perfects early PEN→ULT vs late PEN→ULT
            if parallel_perfect(
                (early_pen, early_ult, early_ult),
                (late_pen,  late_ult,  late_ult),
                0, 1
            ):
                continue

            # 3. Three-way ULT consonance: Bass + early + late
            if not consonant_vertical([bass_ult, early_ult, late_ult]):
                continue

            # 4. No parallel perfects Bass→early PEN→ULT
            if parallel_perfect(
                (bass_pen,  bass_ult,  bass_ult),
                (early_pen, early_ult, early_ult),
                0, 1
            ):
                continue

            # 5. No parallel perfects Bass→late PEN→ULT
            if parallel_perfect(
                (bass_pen, bass_ult, bass_ult),
                (late_pen, late_ult, late_ult),
                0, 1
            ):
                continue

            # Valid pi values: consonant with early ANT (and Bass ANT) at beat 0
            valid_pi = [
                pi for pi in range(MOD)
                if consonant_vertical([early_ant, pi])
                and consonant_vertical([bass_ant, pi])
            ]

            if valid_pi:
                valid.append((c_bass, c_early, c_late, valid_pi))

    return valid
