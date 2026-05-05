#!/bin/bash
export DJANGO_SETTINGS_MODULE=harmony.settings.local
export SECRET_KEY=local_dev_secret_key
python3 manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); u = User.objects.filter(email='student@harmony.edu').first(); 
if u:
    u.set_password('password123');
    u.save();
    print('SUCCESS');
else:
    print('USER_NOT_FOUND');
"
