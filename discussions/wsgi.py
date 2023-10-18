# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import os

from django.core.wsgi import get_wsgi_application

_ = os.environ.setdefault("DJANGO_SETTINGS_MODULE", "discussions.settings")

application = get_wsgi_application()
