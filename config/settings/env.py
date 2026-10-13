from pathlib import Path
from dotenv import load_dotenv
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = os.environ["DJANGO_SECRET_KEY"]
JWT_SECRET_KEY: str = os.environ["JWT_SECRET_KEY"]

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

DB_CONNECTION_MAX_AGE_SECONDS = os.getenv("DB_CONNECTION_MAX_AGE_SECONDS", 600)

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = os.getenv("DEBUG", "False") == "True"

# DO 47 s.2024 §2 transparency rule: the staff member who validates completed
# rectification works must not be the assigned handler. Set True only for
# single-staff local demos so one account can still resolve reports.
ALLOW_SELF_VALIDATION: bool = os.getenv("ALLOW_SELF_VALIDATION", "False").upper() == "TRUE"

SECURE_SSL_REDIRECT: bool = os.environ["SECURE_SSL_REDIRECT"].upper() == "TRUE"

ALLOWED_HOSTS: list[str] = os.environ["ALLOWED_HOSTS"].split(",")

TRUSTED_ORIGINS: list[str] = os.environ["TRUSTED_ORIGINS"].split(",")

if "runserver" in sys.argv:
    COOKIE_DOMAIN: str|None = None
else:
    COOKIE_DOMAIN: str = os.environ["COOKIE_DOMAIN"]