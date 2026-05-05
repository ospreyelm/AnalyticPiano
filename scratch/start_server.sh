#!/bin/bash
export DJANGO_SETTINGS_MODULE=harmony.settings.local
export SECRET_KEY=local_dev_secret_key
python3 manage.py runserver 8001
