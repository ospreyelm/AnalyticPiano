import pytest
from django.core.management import call_command, CommandError


def test_lanes_identification_is_valid_choice():
    """--lanes identification must be accepted by argparse.

    Previously `choices=["exact","analysis","both"]` rejected it silently
    despite a code branch handling it.
    """
    with pytest.raises(CommandError) as exc:
        # Missing --author triggers CommandError AFTER argparse parses --lanes,
        # so argparse accepting 'identification' is what we're testing.
        call_command("generate_unit1", "--lanes=identification")
    # Error must be about --author, NOT about --lanes.
    assert "--author" in str(exc.value) or "author" in str(exc.value)
