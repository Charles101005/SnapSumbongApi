from datetime import date
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

# Verified Resend sender addresses (full RFC format, incl. display name).
# AUTH = reputation-sensitive mail (OTP/verification, password reset).
# GENERAL = in-app mail to verified users (submissions, status updates, bans).
EMAIL_FROM_AUTH = os.getenv("EMAIL_FROM_AUTH")
EMAIL_FROM_GENERAL = os.getenv("EMAIL_FROM_GENERAL")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = os.getenv("DEBUG", "False") == "True"

SECURE_SSL_REDIRECT: bool = os.environ["SECURE_SSL_REDIRECT"].upper() == "TRUE"

ALLOWED_HOSTS: list[str] = os.environ["ALLOWED_HOSTS"].split(",")

TRUSTED_ORIGINS: list[str] = os.environ["TRUSTED_ORIGINS"].split(",")

if "runserver" in sys.argv:
    COOKIE_DOMAIN: str|None = None
else:
    COOKIE_DOMAIN: str = os.environ["COOKIE_DOMAIN"]

# DO 47 s.2024 compliance scoring: reports created before this date predate
# the SLA/photolog/validation obligations, so they are counted for activity
# but exempt from all scoring components. Override in .env with the date the
# DO 47 rules went live in this deployment (ISO format, e.g. 2025-06-01).
DO47_COMPLIANCE_SINCE: date = date.fromisoformat(
    os.getenv("DO47_COMPLIANCE_SINCE", "2024-04-08")
)