
from pathlib import Path

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
SECRET_KEY = 'fake dev'

BASE_DIR = Path(__file__).resolve().parent.parent


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'HOST': os.environ.get('DATABASE_HOST'),
#         'NAME': os.environ.get('DATABASE_NAME'),
#         'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
#         'USER': os.environ.get('DATABASE_USER'),
#     }
# }

ALLOWED_HOSTS = []
