
from pathlib import Path

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
SECRET_KEY = 'fake dev'

BASE_DIR = Path(__file__).resolve().parent.parent


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
