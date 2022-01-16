import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'discussions.settings')

app = Celery('discussions')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# @signals.setup_logging.connect
# def setup_celery_logging(**kwargs):
#     print("something")
#     from logging.config import dictConfig
#     from django.conf import settings
#     dictConfig(settings.LOGGING)
#     pass

# app.log.setup()
