# Common settings for all environments
import os
from os import path
from glob import glob
import time

import dj_database_url
import psycopg2
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from . import requirejs

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

AUTH_USER_MODEL = "accounts.User"

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = "America/New_York"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# SET PATH INFORMATION #####################################################
ROOT_DIR = path.dirname(path.dirname(path.dirname(path.realpath(__file__))))

# needed?
MEDIA_ROOT = ""
MEDIA_URL = ""
STATIC_ROOT = path.join(ROOT_DIR, "static")

# do not delete
STATIC_URL = "/static/"

# needed?
STATICFILES_DIRS = [
    path.join(ROOT_DIR, "lab", "static"),
]
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Load templates from django app directories
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [path.join(ROOT_DIR, "templates/")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

MIDDLEWARE = (
    "django.middleware.common.CommonMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "cached_auth.Middleware",
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "apps.accounts.backend.EmailAuthenticationBackend",
)

ROOT_URLCONF = "harmony.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "harmony.wsgi.application"

TEMPLATE_DIRS = [
    path.join(ROOT_DIR, "lab", "templates"),
]

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 'django_openid_auth',
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    # Internal Apps
    "apps.accounts",
    "apps.exercises",
    "apps.dashboard",
    "lab",
    # Third parties
    "django_extensions",
    "nested_admin",
    "prettyjson",
    "django_tables2",
    "ckeditor",
    "ckeditor_uploader",
    "bootstrap4",
    "widget_tweaks",
    "django_better_admin_arrayfield",
    "import_export",
    "django_filters"
    # 'django_openid_auth',
)

# DATABASE_URL = os.environ.get('DATABASE_URL')
# conn = psycopg2.connect(DATABASE_URL, sslmode='require')

DATABASES = {"default": dj_database_url.config(conn_max_age=600, ssl_require=True)}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(process)d] [%(levelname)s] %(module)s.%(funcName)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "null": {
            "level": "DEBUG",
            "class": "logging.NullHandler",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "lab": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

REQUIREJS_DEBUG, REQUIREJS_CONFIG = requirejs.configure(ROOT_DIR, STATIC_URL)

DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_ALLOW_NONIMAGE_FILES = False
CKEDITOR_CONFIGS = {
    "limited": {
        "toolbar": [
            # ["Format", "Maximize", "Underline", "SpellChecker", "JustifyRight", "JustifyBlock", "SectionLink"],
            ["Bold", "Italic", "Strike", "Subscript", "Superscript", "RemoveFormat"],
            ["JustifyLeft", "JustifyCenter"],
            ["Link", "Unlink", "SpecialChar"],
            ["NumberedList", "BulletedList", "Indent", "Outdent"],
            ["Undo", "Redo"],
            ["Source"],
        ],
        "height": 100,
        "width": 600,
    },
    "full": {
        "skin": "moono",
        # 'skin': 'office2013',
        "height": 200,
        "toolbar_Basic": [["Source", "-", "Bold", "Italic"]],
        "toolbar_YourCustomToolbarConfig": [
            {
                "name": "document",
                "items": [
                    "Source",
                    "-",
                    "Save",
                    "NewPage",
                    "Preview",
                    "Print",
                    "-",
                    "Templates",
                ],
            },
            {
                "name": "clipboard",
                "items": [
                    "Cut",
                    "Copy",
                    "Paste",
                    "PasteText",
                    "PasteFromWord",
                    "-",
                    "Undo",
                    "Redo",
                ],
            },
            {"name": "editing", "items": ["Find", "Replace", "-", "SelectAll"]},
            {
                "name": "forms",
                "items": [
                    "Form",
                    "Checkbox",
                    "Radio",
                    "TextField",
                    "Textarea",
                    "Select",
                    "Button",
                    "ImageButton",
                    "HiddenField",
                ],
            },
            {
                "name": "basicstyles",
                "items": [
                    "Bold",
                    "Italic",
                    "Underline",
                    "Strike",
                    "Subscript",
                    "Superscript",
                    "-",
                    "RemoveFormat",
                ],
            },
            {
                "name": "paragraph",
                "items": [
                    "NumberedList",
                    "BulletedList",
                    "-",
                    "Outdent",
                    "Indent",
                    "-",
                    "Blockquote",
                    "CreateDiv",
                    "-",
                    "JustifyLeft",
                    "JustifyCenter",
                    "JustifyRight",
                    "JustifyBlock",
                    "-",
                    "BidiLtr",
                    "BidiRtl",
                    "Language",
                ],
            },
            {"name": "links", "items": ["Link", "Unlink", "Anchor"]},
            {
                "name": "insert",
                "items": [
                    "Image",
                    "Flash",
                    "Table",
                    "HorizontalRule",
                    "Smiley",
                    "SpecialChar",
                    "PageBreak",
                    "Iframe",
                ],
            },
            "/",
            {"name": "styles", "items": ["Styles", "Format", "Font", "FontSize"]},
            {"name": "colors", "items": ["TextColor", "BGColor"]},
            {"name": "tools", "items": ["Maximize", "ShowBlocks"]},
            {"name": "about", "items": ["About"]},
            # '/',  # put this to force next toolbar on new line
            {
                "name": "yourcustomtools",
                "items": [
                    # put the name of your editor.ui.addButton here
                    "Preview",
                    "Maximize",
                ],
            },
        ],
        "toolbar": "YourCustomToolbarConfig",  # put selected toolbar config here
        # 'toolbarGroups': [{ 'name': 'document', 'groups': [ 'mode', 'document', 'doctools' ] }],
        # 'height': 291,
        # 'width': '100%',
        # 'filebrowserWindowHeight': 725,
        # 'filebrowserWindowWidth': 940,
        # 'toolbarCanCollapse': True,
        # 'mathJaxLib': '//cdn.mathjax.org/mathjax/2.2-latest/MathJax.js?config=TeX-AMS_HTML',
        "tabSpaces": 4,
        "extraPlugins": ",".join(
            [
                "uploadimage",  # the upload image feature
                # your extra plugins here
                "div",
                "autolink",
                "autoembed",
                "embedsemantic",
                "autogrow",
                # 'devtools',
                "widget",
                "lineutils",
                "clipboard",
                "dialog",
                "dialogui",
                "elementspath",
            ]
        ),
    },
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "DEFAULT_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get(
    "EMAIL_HOST_PASSWORD", "DEFAULT_EMAIL_HOST_PASSWORD"
)
EMAIL_USE_TLS = True

APPEND_SLASH = True

ENVIRONMENT_LOCAL = "local"
ENVIRONMENT_DEV = "dev"
ENVIRONMENT_PROD = "prod"

SENTRY_DSN = os.environ.get("SENTRY_DSN")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_viewcache",
    }
}
