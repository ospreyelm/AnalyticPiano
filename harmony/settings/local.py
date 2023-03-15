from harmony.settings.common import *  # NOQA

DEBUG = True

# moved from common.py March 2023
# this is not the most secure solution
SECRET_KEY = os.environ.get("SECRET_KEY", "DEFAULT_SECRET_KEY")

ALLOWED_HOSTS = ["0.0.0.0", "localhost", "127.0.0.1"]

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=ENVIRONMENT_LOCAL,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True,
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "harmony",
        "USER": "postgres",
        "PASSWORD": "password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
