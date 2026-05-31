from apps.exercises.compendium_inverse import (
    compare_realized_notes,
    realize_example_from_clausulae,
)
from apps.exercises.compendium_source import load_cadence_examples


def test_realize_example_from_clausulae_round_trips_notes_and_adds_z7():
    example = next(e for e in load_cadence_examples() if e["id"] == "m145-146")

    realized = realize_example_from_clausulae(example)

    assert compare_realized_notes(example["notes"], realized) == []
    assert realized["staff6"][0]["z7"] == 0
    assert realized["staff5"][3]["z7"] == 1


def test_all_vendored_cadence_examples_round_trip_through_clausulae_realizer():
    failures = []
    for example in load_cadence_examples():
        realized = realize_example_from_clausulae(example)
        differences = compare_realized_notes(example["notes"], realized)
        if differences:
            failures.append((example["id"], differences[:3]))

    assert failures == []
