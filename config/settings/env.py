from pathlib import Path
from dotenv import load_dotenv
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = os.getenv("DEBUG", "False") == "True"

SECURE_SSL_REDIRECT: bool = os.getenv("SECURE_SSL_REDIRECT", "False") == "True"

ALLOWED_HOSTS: list[str] = os.getenv("ALLOWED_HOSTS").split(",")

TRUSTED_ORIGINS: list[str] = os.getenv("TRUSTED_ORIGINS").split(",")

if "runserver" in sys.argv:
    COOKIE_DOMAIN: str = None
else:
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN")