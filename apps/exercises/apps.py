import os
import sys
import threading

from django.apps import AppConfig


def _warm_music21():
    """Import music21 once in the background so the first exercise request
    doesn't pay its multi-second cold-import cost."""
    try:
        import music21  # noqa: F401
    except Exception:
        # Warmup is best-effort; never let it break startup.
        pass


def _should_warm() -> bool:
    """Only warm in a real long-lived server process, not in tests, migrations,
    or one-shot management commands."""
    argv = sys.argv
    if len(argv) > 1:
        cmd = argv[1]
        if cmd == "runserver":
            # Under runserver's autoreloader, ready() fires twice; only warm in
            # the child process that actually serves requests.
            return os.environ.get("RUN_MAIN") == "true"
        # Any other management command (migrate, test, shell, collectstatic, …):
        # don't warm.
        return False
    # No subcommand in argv → WSGI/gunicorn server process: warm.
    return True


def register_psycopg_json_casting(raw_connection):
    if raw_connection is None:
        return

    module_name = getattr(raw_connection.__class__, "__module__", "")
    if module_name.startswith("psycopg2"):
        import psycopg2.extras

        psycopg2.extras.register_default_json(
            conn_or_curs=raw_connection, loads=lambda x: x
        )
        psycopg2.extras.register_default_jsonb(
            conn_or_curs=raw_connection, loads=lambda x: x
        )
        return

    if module_name.startswith("psycopg"):
        from psycopg.types.json import set_json_loads

        set_json_loads(lambda x: x, raw_connection)


class ExercisesConfig(AppConfig):
    name = "apps.exercises"
    verbose_name = "Content"

    def ready(self):
        from django.db.backends.signals import connection_created

        def disable_psycopg2_json_casting(sender, connection, **kwargs):
            # Django's built-in JSONField decodes JSON itself.
            # psycopg2 2.9+ auto-casts both json and jsonb columns to Python
            # dicts/lists, which breaks Django's json.loads() call.
            # Return raw strings so Django can decode them.
            register_psycopg_json_casting(connection.connection)

        connection_created.connect(disable_psycopg2_json_casting)

        if _should_warm():
            threading.Thread(
                target=_warm_music21, name="music21-warmup", daemon=True
            ).start()
