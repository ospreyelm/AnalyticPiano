from django.apps import AppConfig


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
            import psycopg2.extras
            psycopg2.extras.register_default_json(
                conn_or_curs=connection.connection, loads=lambda x: x
            )
            psycopg2.extras.register_default_jsonb(
                conn_or_curs=connection.connection, loads=lambda x: x
            )

        connection_created.connect(disable_psycopg2_json_casting)
