import pytest

from apps.exercises.clausulae_titles import page_title, student_title, short_description


def test_simple_three_voices():
    assert page_title("simple", 3) == "Simple Cadences in Three Voices"


def test_compound_two_and_three():
    assert page_title("compound", 2) == "Compound Cadences in Two Voices"
    assert page_title("compound", 3) == "Compound Cadences in Three Voices"


def test_double_four_voices():
    assert page_title("double", 4) == "Double Cadences in Four Voices"


def test_compound_four_voice_figure_variants():
    assert page_title("compound", 4, upper_figures={5, 4}) == "Compound Cadences with 5/4 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 5}) == "Compound Cadences with 6/5 in Four Voices"
    assert page_title("compound", 4, upper_figures={6, 4}) == "Compound Cadences with 6/4 in Four Voices"


def test_compound_four_voice_default_when_unknown():
    assert page_title("compound", 4, upper_figures={2, 7}) == "Compound Cadences with 6/4 in Four Voices"


def test_student_title_is_page_title_plus_key():
    assert student_title("simple", 3, key="C") == "Simple Cadences in Three Voices in C major"


def test_short_description_fits_60_and_is_unique():
    # Even the longest page_title family must yield a <=60 char description.
    d1 = short_description("compound", 4, key="Bb", unit=12, fingerprint="D:D-Ti-D A:S-Fa-M T:M-Re-D B:D-Sol-D")
    d2 = short_description("compound", 4, key="Bb", unit=12, fingerprint="D:D-Ti-D A:S-La-S T:M-Re-M B:D-Sol-D")
    assert len(d1) <= 60
    assert d1 != d2  # different fingerprints -> different keys
    assert d1.startswith("RfC u12 compound 4v Bb ")


def test_short_description_is_stable():
    args = dict(key="C", unit=9, fingerprint="D:D-Ti-D B:D-Sol-D")
    assert short_description("simple", 3, **args) == short_description("simple", 3, **args)
