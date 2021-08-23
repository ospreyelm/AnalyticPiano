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
