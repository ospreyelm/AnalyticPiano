from django.shortcuts import render

from apps.exercises.local_tools import get_database_target, require_local_content_tools


def content_generation_view(request):
    require_local_content_tools()
    return render(
        request,
        "tools/content_generation.html",
        {
            "db_target": get_database_target(),
            "result": None,
            "form_data": {
                "author": "",
                "unit": "9",
                "riemenschneider": "1-30",
                "mode": "roman",
            },
        },
    )
