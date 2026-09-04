from . import env

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases


if not env.DEBUG or (env.DB_NAME and env.DB_USER and env.DB_PASSWORD and env.DB_HOST and env.DB_PORT):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env.DB_NAME,
            'USER': env.DB_USER,
            'PASSWORD': env.DB_PASSWORD,
            'HOST': env.DB_HOST,
            'PORT': env.DB_PORT,

            'OPTIONS': {
                'sslmode': 'disable' if env.DEBUG else 'require',
            },
            'CONN_MAX_AGE': int(env.DB_CONNECTION_MAX_AGE_SECONDS)
        }
    }

else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': env.BASE_DIR / 'db.sqlite3',
        }
    }