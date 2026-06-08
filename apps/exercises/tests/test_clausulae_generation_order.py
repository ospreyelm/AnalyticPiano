from apps.exercises.management.commands import generate_clausulae_b1


def test_all_branch_b_playlists_are_key_interleaved():
    for unit in generate_clausulae_b1.ALL_UNITS:
        generator = generate_clausulae_b1._GENERATORS[unit]

        assert "_interleave_key_blocks" in generator.__code__.co_names, (
            f"{generator.__name__} must interleave generated key blocks before "
            "building its student playlist"
        )


def test_interleave_key_blocks_cycles_keys_before_next_pattern():
    items = [
        "C pattern 1",
        "C pattern 2",
        "G pattern 1",
        "G pattern 2",
        "F pattern 1",
        "F pattern 2",
    ]

    assert generate_clausulae_b1._interleave_key_blocks(items, key_count=3) == [
        "C pattern 1",
        "G pattern 1",
        "F pattern 1",
        "C pattern 2",
        "G pattern 2",
        "F pattern 2",
    ]


def test_interleave_key_blocks_leaves_uneven_input_unchanged():
    items = ["C pattern 1", "C pattern 2", "G pattern 1"]

    assert generate_clausulae_b1._interleave_key_blocks(items, key_count=2) == items
