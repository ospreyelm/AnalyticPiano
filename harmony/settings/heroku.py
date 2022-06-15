import os
import json
from harmony.settings.common import *

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = json.loads(os.environ.get('ALLOWED_HOSTS', '[]'))

LTI_OAUTH_CREDENTIALS = json.loads(os.environ.get('LTI_OAUTH_CREDENTIALS', '{}'))

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],

        environment=ENVIRONMENT_PROD,

        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,

        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True
    )
