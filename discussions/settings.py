import logging
import os
from pathlib import Path

import sentry_sdk
from django.conf.locale.en import formats as en_formats
from django.contrib.messages import constants as messages
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

APP_DOMAIN = os.getenv("DISCUSSIONS_DOMAIN", "discu.eu")
APP_SCHEME = "https"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    os.environ.get("ALLOWED_HOST"),
    APP_DOMAIN,
]
CSRF_COOKIE_DOMAIN = APP_DOMAIN
CSRF_TRUSTED_ORIGINS = [
    "https://*.xojoc.pw",
    f"https://{APP_DOMAIN}",
    "http://localhost:7777",
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django_celery_beat",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "web.apps.WebConfig",
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # "allauth.apple",
    # "allauth.github",
    # "allauth.feedly",
    # "allauth.google",
    # "allauth.reddit",
    # "allauth.twitter",
    "debug_toolbar",
    "django.contrib.sitemaps",
    "ninja",
    "django_extensions",
]

if os.environ.get("DJANGO_DEVELOPMENT"):
    INSTALLED_APPS.append("django_sass")

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "web.middleware.CORSMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "/"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = APP_SCHEME
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
# ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_PRESERVE_USERNAME_CASING = False
ACCOUNT_USERNAME_MIN_LENGTH = 5
ACCOUNT_USERNAME_REQUIRED = False
LOGIN_URL = "/account/login/"
LOGIN_REDIRECT_URL = "/dashboard"

SITE_ID = 1


ROOT_URLCONF = "discussions.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "environment": "web.jinja2.environment",
        },
    },
]

WSGI_APPLICATION = "discussions.wsgi.application"

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        # "ENGINE": "django_postgrespool2",
        "HOST": os.environ.get("DATABASE_HOST"),
        "NAME": os.environ.get("DATABASE_NAME"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD"),
        "USER": os.environ.get("DATABASE_USER"),
    }
}

# DATABASE_POOL_CLASS = "sqlalchemy.pool.QueuePool"

# DATABASE_POOL_ARGS = {
#     "max_overflow": 50,
#     "pool_size": 50,
#     "recycle": 300,
# }

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "web.CustomUser"


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# todo: re introduce manifest
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"


USERAGENT = "Discu.eu bot/0.1"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL"),
        "KEY_PREFIX": "discussions:django_cache",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

APP_CELERY_TASK_MAX_TIME = 30  # seconds

CELERY_BROKER_URL = os.getenv("REDIS_URL")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL")

task_ignore_result = True

CELERY_BROKER_TRANSPORT_OPTIONS = {
    "fanout_patterns": True,
    "fanout_prefix": True,
    "visibility_timeout": 43200,
    # 'global_keyprefix': 'discussions_celery:',
}

CELERYD_HIJACK_ROOT_LOGGER = False
CELERY_TASK_ACKS_LATE = False
celery_task_acks_late = False
CELERYD_PREFETCH_MULTIPLIER = 1

CELERY_WORKER_ENABLE_REMOTE_CONTROL = True

# xojoc: find a way to create default schedules for freshly installed apps
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


def change_404_level_to_INFO(record):
    if record.status_code == 404:
        record.levelname = "INFO"
    return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "filters": {
        "change_404_to_info": {
            "()": "django.utils.log.CallbackFilter",
            "callback": change_404_level_to_INFO,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
        "null": {
            "class": "logging.NullHandler",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO", "formatter": "simple"},
    "loggers": {
        "celery": {
            "handlers": ["console", "mail_admins"],
            "level": "WARNING",
            # "propagate": True,
        },
        "celery.task": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            # "propagate": True,
        },
        "web": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
            "filters": ["change_404_to_info"],
        },
        "daphne": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "requests": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "urllib3": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

if os.environ.get("DJANGO_DEVELOPMENT"):
    LOGGING["loggers"]["web"]["level"] = "DEBUG"
    LOGGING["loggers"]["web"]["handlers"] = ["console"]
    LOGGING["loggers"]["django.request"]["handlers"] = ["console"]
    # LOGGING['loggers']['prawcore'] = {'level': 'DEBUG'}
    # LOGGING['loggers']['psycopg2'] = {'level': 'DEBUG'}
    # LOGGING['loggers']['django.db.backends'] = {'level': 'DEBUG'}

if not os.environ.get("DJANGO_DEVELOPMENT"):
    sentry_logging = LoggingIntegration(
        level=logging.WARNING,
        event_level=logging.ERROR,
    )

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            sentry_logging,
        ],
    )

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

en_formats.DATE_FORMAT = "j/n/Y"
en_formats.DATETIME_FORMAT = "H:i:s j/n/Y"

INTERNAL_IPS = ["127.0.0.1"]

ADMINS = [("xojoc", "hi@xojoc.pw")]
MANAGERS = ADMINS
SERVER_EMAIL = "hi@discu.eu"

EMAIL_HOST = "smtp.fastmail.com"
EMAIL_PORT = "465"
EMAIL_HOST_USER = os.getenv("EMAIL_SMTP_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_SMTP_PASSWORD")
EMAIL_USE_SSL = True
DEFAULT_FROM_EMAIL = "hi@discu.eu"
EMAIL_IMAP_HOST = "imap.fastmail.com"
EMAIL_IMAP_MAILBOX = "discueu"
EMAIL_IMAP_USER = os.getenv("EMAIL_IMAP_USER")
EMAIL_IMAP_PASSWORD = os.getenv("EMAIL_IMAP_PASSWORD")
EMAIL_TO_PREFIX = ""

STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PLAN_PRICE_API_ID = os.getenv("STRIPE_PLAN_PRICE_API_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


MESSAGE_TAGS = {
    messages.ERROR: "danger",
}

SHELL_PLUS_IMPORTS = [
    "from web import *",
    "from importlib import reload",
    "import os",
]

if os.environ.get("DJANGO_DEVELOPMENT"):
    from .settings_dev import *  # noqa F401, F403
