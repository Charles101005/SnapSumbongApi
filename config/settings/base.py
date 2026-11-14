import os

from .env import *
from .apps import *
from .auth import *
from .database import *
from .drf import *
from .middleware import *
from .security import *


if DEBUG:
    #dev dependencies
    INSTALLED_APPS += [
        'django_extensions',
        'devutils',
    ]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR/'external'/'email'/'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Wall-clock timezone for every date lookup (created_at__date, TruncDate),
# "today" bucket, report-number stamp and email timestamp. The product serves
# Philippine LGUs, so it must match the calendar day staff see in the browser
# (UTC+8). A UTC default made the "Today" filter miss reports created between
# 00:00 and 08:00 local time, because their UTC timestamp still falls on the
# previous day. Override per deployment with the TIME_ZONE env var.
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Manila')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # populated by collectstatic in the container

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
