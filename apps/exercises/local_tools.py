from django.conf import settings
from django.http import Http404


def require_local_content_tools():
    if not getattr(settings, "ENABLE_LOCAL_CONTENT_TOOLS", False):
        raise Http404("Local content tools are disabled.")


def get_database_target():
    database = settings.DATABASES["default"]
    return {
        "engine": database.get("ENGINE", ""),
        "host": database.get("HOST") or "localhost",
        "port": str(database.get("PORT", "")),
        "name": database.get("NAME", ""),
    }
