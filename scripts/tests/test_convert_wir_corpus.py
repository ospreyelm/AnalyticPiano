# scripts/tests/test_convert_wir_corpus.py
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# We import the parser function we're about to write
from convert_wir_corpus import parse_wir_file


def _parse(text):
    """Helper: parse embedded text as if it were a WiR file."""
    return parse_wir_file(text, riemenschneider=1)


def test_anacrusis():
    result = _parse("Composer: Bach\nBWV: 269\nTime Signature: 3/4\n\nm0 b3 G: I\n")
    labels = result["labels"]
    assert len(labels) == 1
    assert labels[0] == {"measure": 0, "beat": 3.0, "label": "I", "local_key": "G"}


def test_beat_marker_parsed():
    result = _parse("BWV: 269\nTime Signature: 4/4\n\nm1 I b2 IV b2.5 V6\n")
    labels = result["labels"]
    assert labels[0] == {"measure": 1, "beat": 1.0, "label": "I",  "local_key": "?"}
    assert labels[1] == {"measure": 1, "beat": 2.0, "label": "IV", "local_key": "?"}
    assert labels[2] == {"measure": 1, "beat": 2.5, "label": "V6", "local_key": "?"}


def test_key_change_updates_local_key():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm5 G: I\nm6 d: i b2 V\n")
    labels = result["labels"]
    assert labels[0]["local_key"] == "G"
    assert labels[1]["local_key"] == "d"
    assert labels[2]["local_key"] == "d"


def test_key_change_token_not_emitted_as_label():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm1 G: I\n")
    labels = result["labels"]
    assert len(labels) == 1
    assert labels[0]["label"] == "I"


def test_flat_rn_not_confused_with_beat_marker():
    # bVI starts with 'b' but is not a beat marker (no digit after 'b')
    result = _parse("BWV: 269\nTime Signature: 4/4\n\nm1 bVI b2 iv\n")
    labels = result["labels"]
    assert labels[0]["label"] == "bVI"
    assert labels[0]["beat"] == 1.0
    assert labels[1]["label"] == "iv"
    assert labels[1]["beat"] == 2.0


def test_repeat_barlines_skipped():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm4 V || b3 I\n")
    labels = result["labels"]
    labels_only = [l["label"] for l in labels]
    assert "||" not in labels_only
    assert "V" in labels_only
    assert "I" in labels_only


def test_variant_attaches_to_main_label():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm11 vi b2 iii6\nm11var1 vi b2 I6/4\n")
    labels = result["labels"]
    # m11 b2: main=iii6, variant=I6/4
    b2 = next(l for l in labels if l["measure"] == 11 and l["beat"] == 2.0)
    assert b2["label"] == "iii6"
    assert b2.get("variant") == "I6/4"


def test_header_lines_skipped():
    result = _parse(
        "Composer: J. S. Bach\nBWV: 269\nTitle: Test\nAnalyst: Jones\n"
        "Proofreader: Smith\nNote: something\nTime Signature: 3/4\nForm: chorale\n\nm1 I\n"
    )
    labels = result["labels"]
    assert len(labels) == 1


def test_bwv_extracted_from_header():
    result = _parse("BWV: 269\nTime Signature: 3/4\n\nm1 I\n")
    assert result["bwv"] == "269"


def test_title_extracted_from_header():
    result = _parse("Title: Aus meines Herzens Grunde\nBWV: 269\nTime Signature: 3/4\n\nm1 I\n")
    assert result["title"] == "Aus meines Herzens Grunde"
