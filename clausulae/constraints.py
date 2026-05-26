"""
Constraint checkers for simple and compound clausula cadences.
Operates purely in Z₇ — no note names.
"""

from .core import z7, interval, MOD


def parallel_perfect(c1, c2, pos1, pos2):
    """
    True if parallel perfect fifths/octaves exist between two voices
    moving from pos1 to pos2.
    """
    v1_move = interval(c1[pos1], c1[pos2])
    v2_move = interval(c2[pos1], c2[pos2])
    simultaneous_interval = interval(c1[pos1], c2[pos1])

    if v1_move == v2_move:
        if simultaneous_interval in (0, 3, 4):
            return True
    return False


def has_parallel_perfects(c1, c2):
    """Check ANT→PEN and PEN→ULT for parallel perfect intervals."""
    if parallel_perfect(c1, c2, 0, 1):
        return True
    if parallel_perfect(c1, c2, 1, 2):
        return True
    return False


def consonant_vertical(degrees):
    """
    True if simultaneous scale degrees form an acceptable sonority.
    Seconds (interval 1 in either direction) are dissonant. All else passes.
    """
    degs = list(degrees)
    for i in range(len(degs)):
        for j in range(i + 1, len(degs)):
            iv = interval(degs[i], degs[j])
            iv_inv = interval(degs[j], degs[i])
            if min(iv, iv_inv) == 1:
                return False
    return True


def bass_constraint_ok(voices):
    """Bass Clausula must be in the lowest-indexed voice (voice 0)."""
    for i, (name, _, _) in enumerate(voices):
        if name == "Bass" and i != 0:
            return False
    return True


def distinctness_ok(triples):
    """No two voices share the same triple."""
    return len(set(triples)) == len(triples)


def same_type_parallel_ok(v1, v2):
    """
    Two voices of the same clausula type may not share their ANT or ULT.
    Shared ANT/ULT produces parallel unisons/octaves at outer positions.
    Returns True if the pair is OK.
    """
    if v1[0] != v2[0]:
        return True
    a1, p1, u1 = v1[2]
    a2, p2, u2 = v2[2]
    if z7(a1) == z7(a2):
        return False
    if z7(u1) == z7(u2):
        return False
    return True


def validate_simple(voices):
    """
    voices: list of (type_name, variant_idx, triple)
    Returns (valid: bool, reasons: list of str)
    """
    from itertools import combinations
    from .core import SOLFEGE

    reasons = []
    triples = [v[2] for v in voices]

    if not distinctness_ok(triples):
        reasons.append("distinctness violated")

    if not bass_constraint_ok(voices):
        reasons.append("Bass Clausula not in lowest voice")

    for (i, v1), (j, v2) in combinations(enumerate(voices), 2):
        if not same_type_parallel_ok(v1, v2):
            reasons.append(
                f"same-type parallel at ANT or ULT: voice {i+1} ({v1[0]} var.{v1[1]+1}) "
                f"vs voice {j+1} ({v2[0]} var.{v2[1]+1})"
            )

    for (i, v1), (j, v2) in combinations(enumerate(voices), 2):
        if has_parallel_perfects(v1[2], v2[2]):
            reasons.append(f"parallel perfects: voice {i+1} ({v1[0]}) vs voice {j+1} ({v2[0]})")

    for pos, label in [(0, "ANT"), (1, "PEN"), (2, "ULT")]:
        degs = [t[pos] for t in triples]
        if not consonant_vertical(degs):
            reasons.append(f"dissonant vertical at {label}: {[SOLFEGE[d] for d in degs]}")

    return len(reasons) == 0, reasons
