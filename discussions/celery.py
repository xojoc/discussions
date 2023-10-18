# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import os

from celery import Celery

_ = os.environ.setdefault("DJANGO_SETTINGS_MODULE", "discussions.settings")

app = Celery("discussions")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
