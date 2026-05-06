from django.conf import settings
from django.http import Http404


def require_local_content_tools_enabled():
    if not getattr(settings, "ENABLE_LOCAL_CONTENT_TOOLS", False):
        raise Http404("Local content tools are disabled.")


def get_local_content_db_target():
    database = settings.DATABASES["default"]
    return {
        "engine": database.get("ENGINE", ""),
        "host": database.get("HOST", ""),
        "port": database.get("PORT", ""),
        "name": database.get("NAME", ""),
    }
