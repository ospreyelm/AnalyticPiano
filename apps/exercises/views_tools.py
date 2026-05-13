from django.core.management import call_command
from django.shortcuts import render

from apps.exercises.local_tools import get_database_target, require_local_content_tools


DEFAULT_FORM_DATA = {
    "author": "",
    "unit": "9",
    "riemenschneider": "1-30",
    "mode": "roman",
    "overwrite": False,
}


def _get_form_data(request):
    if request.method != "POST":
        return dict(DEFAULT_FORM_DATA)

    return {
        "author": request.POST.get("author", "").strip(),
        "unit": request.POST.get("unit", DEFAULT_FORM_DATA["unit"]).strip(),
        "riemenschneider": request.POST.get(
            "riemenschneider",
            DEFAULT_FORM_DATA["riemenschneider"],
        ).strip(),
        "mode": request.POST.get("mode", DEFAULT_FORM_DATA["mode"]).strip(),
        "overwrite": request.POST.get("overwrite") == "on",
    }


def content_generation_view(request):
    require_local_content_tools()
    form_data = _get_form_data(request)
    messages = []
    result = None

    if request.method == "POST":
        command = request.POST.get("command", "").strip()
        author = form_data["author"]

        if not author:
            messages.append(
                {
                    "level": "error",
                    "text": "Author email is required.",
                }
            )
        else:
            try:
                if command == "generate_unit1":
                    call_command("generate_unit1", author=author)
                elif command == "generate_unit2_meter_exercises":
                    call_command(
                        "generate_unit2_meter_exercises",
                        author=author,
                        public=True,
                    )
                elif command == "create_unit_playlist":
                    try:
                        unit = int(form_data["unit"])
                    except (TypeError, ValueError):
                        unit = None

                    if unit is None:
                        messages.append(
                            {
                                "level": "error",
                                "text": "Unit must be a whole number.",
                            }
                        )

                    if not form_data["riemenschneider"]:
                        messages.append(
                            {
                                "level": "error",
                                "text": "Riemenschneider range is required.",
                            }
                        )

                    if not form_data["mode"]:
                        messages.append(
                            {
                                "level": "error",
                                "text": "Mode is required.",
                            }
                        )

                    if not messages:
                        call_command(
                            "create_unit_playlist",
                            unit=unit,
                            riemenschneider=form_data["riemenschneider"],
                            mode=form_data["mode"],
                            author=author,
                            public=True,
                            overwrite=form_data["overwrite"],
                        )
                else:
                    messages.append(
                        {
                            "level": "error",
                            "text": "Unknown command.",
                        }
                    )

                if not messages:
                    result = {
                        "status": "success",
                        "command": command,
                    }
                    messages.append(
                        {
                            "level": "success",
                            "text": "Command completed successfully.",
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - return surfaced command errors to local UI.
                result = {
                    "status": "error",
                    "command": command,
                }
                messages.append(
                    {
                        "level": "error",
                        "text": str(exc),
                    }
                )

    return render(
        request,
        "tools/content_generation.html",
        {
            "db_target": get_database_target(),
            "result": result,
            "messages": messages,
            "form_data": form_data,
        },
    )
