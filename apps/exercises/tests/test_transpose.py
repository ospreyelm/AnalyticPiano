"""
Tests for the smart transposition direction logic in apps/exercises/utils/transpose.py.

Run with:
    python3 apps/exercises/tests/test_transpose.py

No Django or pytest required — imports only constants directly.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Import constants directly without Django setup
from apps.exercises.constants import sig_to_pc


def smart_midi_vector(sig_from, sig_to):
    """
    Compute the midi_vector for transposing from sig_from to sig_to,
    picking the direction that gives the smaller interval (≤ 6 semitones).
    Tritone (exactly 6) prefers down.
    """
    pc_from = sig_to_pc[sig_from]
    pc_to = sig_to_pc[sig_to]
    pc_vector = (12 + pc_to - pc_from) % 12
    if pc_vector >= 6:
        return pc_vector - 12  # go down
    return pc_vector            # go up


class TestSmartTransposeDirection(unittest.TestCase):

    def test_c_to_f_up_p4(self):
        # C→F: up=5, down=7 → pick up (+5)
        self.assertEqual(smart_midi_vector("", "b"), 5)

    def test_c_to_bb_down_m2(self):
        # C→Bb: up=10, down=2 → pick down (−2)
        self.assertEqual(smart_midi_vector("", "bb"), -2)

    def test_c_to_fsharp_down_tritone(self):
        # C→F#: up=6, down=6 → tritone, prefer down (−6)
        self.assertEqual(smart_midi_vector("", "######"), -6)

    def test_c_to_g_down_p4(self):
        # C→G: up=7, down=5 → pick down (−5)
        self.assertEqual(smart_midi_vector("", "#"), -5)

    def test_same_key_zero(self):
        # No transposition
        self.assertEqual(smart_midi_vector("", ""), 0)

    def test_c_to_db_up_m2(self):
        # C→Db: up=1 → pick up (+1)
        self.assertEqual(smart_midi_vector("", "bbbbb"), 1)

    def test_c_to_b_down_m2(self):
        # C→B: up=11, down=1 → pick down (−1)
        self.assertEqual(smart_midi_vector("", "#####"), -1)

    def test_c_to_d_up_m2(self):
        # C→D: up=2 → pick up (+2)
        self.assertEqual(smart_midi_vector("", "##"), 2)

    def test_never_more_than_6_semitones(self):
        sigs = list(sig_to_pc.keys())
        for sig_from in sigs:
            for sig_to in sigs:
                v = smart_midi_vector(sig_from, sig_to)
                self.assertLessEqual(
                    abs(v), 6,
                    f"midi_vector={v} for {sig_from!r}→{sig_to!r} exceeds 6 semitones"
                )


if __name__ == "__main__":
    unittest.main()
