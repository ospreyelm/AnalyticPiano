release: python manage.py migrate && python manage.py createcachetable
web: gunicorn harmony.wsgi:application --log-file -
