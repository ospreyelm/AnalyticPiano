from io import StringIO

from django.core.management import call_command


def test_verify_compendium_realization_command_reports_success():
    out = StringIO()

    call_command("verify_compendium_realization", stdout=out)

    text = out.getvalue()
    assert "Verified" in text
    assert "mismatches=0" in text
