# Amazon Web Services (AWS) settings
from harmony.settings.common import *

LTI_OAUTH_CREDENTIALS = {
    "harmonykey": "harmonysecret",
}

INSTALLED_APPS += ("debug_toolbar",)

MIDDLEWARE += ("debug_toolbar.middleware.DebugToolbarMiddleware",)
