"""
clausulae — formal clausulae as mathematical objects in Z₇.
"""

from .core import (
    ALL_CLAUSULAE,
    CLAUSULA_COLOR,
    CLAUSULAE,
    MOD,
    SOLFEGE,
    diatonic_fifth,
    interval,
    show,
    z7,
)
from .constraints import (
    bass_constraint_ok,
    consonant_vertical,
    distinctness_ok,
    has_parallel_perfects,
    parallel_perfect,
    same_type_parallel_ok,
    validate_simple,
)
from .generate import enumerate_compound, enumerate_compound_3voice, enumerate_compound_3voice_double_tau1, enumerate_compound_4voice, enumerate_simple
from .realize import key_realize, pitch_to_z7, score_cadence

__all__ = [
    # core
    "MOD", "SOLFEGE", "CLAUSULAE", "ALL_CLAUSULAE", "CLAUSULA_COLOR",
    "z7", "interval", "diatonic_fifth", "show",
    # constraints
    "parallel_perfect", "has_parallel_perfects", "consonant_vertical",
    "bass_constraint_ok", "distinctness_ok", "same_type_parallel_ok",
    "validate_simple",
    # generate
    "enumerate_simple", "enumerate_compound", "enumerate_compound_3voice",
    "enumerate_compound_3voice_double_tau1", "enumerate_compound_4voice",
    # realize
    "key_realize", "pitch_to_z7", "score_cadence",
]
