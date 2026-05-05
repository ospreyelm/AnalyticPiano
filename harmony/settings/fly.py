import os
import json
from harmony.settings.common import *

DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = json.loads(os.environ.get("ALLOWED_HOSTS", "[]"))

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=ENVIRONMENT_PROD,
        traces_sample_rate=1.0,
        send_default_pii=True,
    )
