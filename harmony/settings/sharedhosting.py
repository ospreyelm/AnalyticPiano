import os
from harmony.settings.common import *

DEBUG = False
ALLOWED_HOSTS = []  # Required when Debug=False
FORCE_SCRIPT_NAME = None
STATIC_URL = "/static/"

# Update the requirejs configuration to use the modified STATIC_URL
REQUIREJS_DEBUG, REQUIREJS_CONFIG = requirejs.configure(ROOT_DIR, STATIC_URL)

# For proper security, the file referenced below ought to be encrypted.
with open(os.path.join(BASE_DIR.parent.absolute(), "django_secret_for_AnalyticPiano.txt")) as f:
    SECRET_KEY = f.read().strip()

print('Running sharedhosting.py')
