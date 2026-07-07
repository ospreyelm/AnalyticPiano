import os
import django

def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.local")
    django.setup()
    from django.test.utils import setup_test_environment

    try:
        setup_test_environment()
    except RuntimeError:
        # Already set up by another discovered conftest.py in this same
        # pytest session (harmless -- Django's test environment is global).
        pass
