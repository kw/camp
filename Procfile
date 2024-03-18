web: gunicorn config.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery -A config worker -l info --concurrency 2
