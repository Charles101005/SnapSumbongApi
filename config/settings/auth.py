from datetime import timedelta

import cloudinary

from . import env

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = "apps_accounts.Users"


SIMPLE_JWT = {
    'SIGNING_KEY': env.JWT_SECRET_KEY,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    "USER_ID_FIELD": "user_id",
}

VERIFICATION_REQUEST_CONFIG = {
    'OTP_LENGTH': 4,
    'MAX_ATTEMPTS': 3,
    'MAX_RESENDS': 2,
    'RESEND_COOLDOWN': timedelta(minutes=1),
    'VERIFICATION_REQUEST_LIFETIME': timedelta(minutes=1),
    'ABANDONED_THRESHOLD': timedelta(hours=1),
}

STORAGE_CONFIG ={
    'MAX_SIGNATURE_COUNT': 5,
    'EXPIRES_IN': timedelta(minutes=15),
}



