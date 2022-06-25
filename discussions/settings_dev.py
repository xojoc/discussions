from pathlib import Path
from django.contrib.messages import constants as message_constants


DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
APP_DOMAIN = "localhost:7777"
APP_SCHEME = "http"
SECRET_KEY = "fake dev"

BASE_DIR = Path(__file__).resolve().parent.parent

CSRF_COOKIE_DOMAIN = "localhost"
CSRF_COOKIE_SECURE = False

MESSAGE_LEVEL = message_constants.DEBUG

EMAIL_TO_PREFIX = "dev__"


ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
