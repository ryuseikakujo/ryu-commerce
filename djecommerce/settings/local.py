from .base import *

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1']


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'djcommerce',
#         'USER': 'admin',
#         'PASSWORD' : 'admin',
#         'HOST' : 'localhost',
#         'PORT' : 5432,
#     }
# }

DATABASES = {
    'default': env.db(),
}