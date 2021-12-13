from pathlib import Path

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
SECRET_KEY = 'fake dev'

BASE_DIR = Path(__file__).resolve().parent.parent

CSRF_COOKIE_DOMAIN = 'localhost'
CSRF_COOKIE_SECURE = False

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'HOST': os.environ.get('DATABASE_HOST'),
#         'NAME': os.environ.get('DATABASE_NAME'),
#         'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
#         'USER': os.environ.get('DATABASE_USER'),
#     }
# }
