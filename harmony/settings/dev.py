# Local development settings
from harmony.settings.common import *

INSTALLED_APPS += (
#    'debug_toolbar',  # Requires django-debug-toolbar>=2.2
#    'sslserver',      # Requires django-sslserver>=0.22
)

MIDDLEWARE += (
#    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],

        environment=ENVIRONMENT_DEV,

        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,

        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True
    )
