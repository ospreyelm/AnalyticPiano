import os
import django

def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.local")
    django.setup()
    from django.test.utils import setup_test_environment

    setup_test_environment()
