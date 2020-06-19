# Local development settings
from harmony.settings.common import *

INSTALLED_APPS += (
#    'debug_toolbar',  # Requires django-debug-toolbar>=2.2
#    'sslserver',      # Requires django-sslserver>=0.22
)

MIDDLEWARE += (
#    'debug_toolbar.middleware.DebugToolbarMiddleware',
)
