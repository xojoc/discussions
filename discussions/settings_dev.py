from pathlib import Path


DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
SECRET_KEY = 'fake dev'

BASE_DIR = Path(__file__).resolve().parent.parent

CSRF_COOKIE_DOMAIN = 'localhost'
CSRF_COOKIE_SECURE = False
