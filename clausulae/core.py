"""
Z₇ arithmetic and clausula definitions.
All pitch class logic lives here. No note names, no music21.
"""

# ── Z₇ arithmetic ─────────────────────────────────────────────────────────────

MOD = 7

def z7(n):
    return n % MOD

def interval(a, b):
    """Directed interval from a to b in Z₇ (ascending = positive)."""
    return z7(b - a)

def diatonic_fifth(i):
    """Is this interval a perfect fifth (4) or fourth (3) in Z₇?"""
    return i in (3, 4)

# ── Solfège display ───────────────────────────────────────────────────────────

SOLFEGE = {0: "Do", 1: "Re", 2: "Mi", 3: "Fa", 4: "Sol", 5: "La", 6: "Ti"}

def show(triple):
    a, p, u = triple
    return f"{SOLFEGE[a]}–{SOLFEGE[p]}–{SOLFEGE[u]}"

# ── Clausula definitions ──────────────────────────────────────────────────────

CLAUSULAE = {
    "Discant": [
        (0, 6, 0),                          # Do–Ti–Do
    ],
    "Tenor": [
        (0, 1, 0),                          # Do–Re–Do
        (0, 1, 2),                          # Do–Re–Mi
        (2, 1, 0),                          # Mi–Re–Do
        (2, 1, 2),                          # Mi–Re–Mi
    ],
    "Alto": [
        (4, 4, 4),                          # Sol–Sol–Sol
        (4, 3, 2),                          # Sol–Fa–Mi
        (4, 5, 4),                          # Sol–La–Sol
    ],
    "Bass": [
        (0, 4, 0),                          # Do–Sol–Do
    ],
}

# ── Notation colors ───────────────────────────────────────────────────────────
# Remeš Compendium color scheme. Used when generating score output.
# Future per-example XMLs should assign these programmatically from clausula
# type, not inherit Sibelius export colors (which are inconsistent).

CLAUSULA_COLOR = {
    "Discant": "#F9141B",
    "Tenor":   "#108040",
    "Alto":    "#1B4FD8",
    "Bass":    "#1A1B1E",
    "Unknown": "#1A1B1E",
}

# All clausulae as (type_name, variant_index, triple)
ALL_CLAUSULAE = [
    (name, i, triple)
    for name, triples in CLAUSULAE.items()
    for i, triple in enumerate(triples)
]
