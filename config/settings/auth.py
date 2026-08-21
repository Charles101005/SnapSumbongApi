from datetime import timedelta

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
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
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