# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import os

from django.core.asgi import get_asgi_application

_ = os.environ.setdefault("DJANGO_SETTINGS_MODULE", "discussions.settings")

application = get_asgi_application()
