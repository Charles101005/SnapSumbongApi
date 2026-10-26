from . import env


SECURE_SSL_REDIRECT: bool = env.SECURE_SSL_REDIRECT

# TLS is terminated by the Caddy reverse proxy (see Caddyfile), which forwards
# requests to Django over plain HTTP and sets X-Forwarded-Proto/X-Forwarded-Host.
# Trust those headers so request.is_secure(), SECURE_SSL_REDIRECT and cookie
# flags behave correctly behind the proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Browsers only send these cookies over HTTPS (always true in production
# behind Caddy; disabled in local DEBUG so plain-HTTP dev still works).
SESSION_COOKIE_SECURE: bool = not env.DEBUG
CSRF_COOKIE_SECURE: bool = not env.DEBUG

SESSION_COOKIE_DOMAIN: str = env.COOKIE_DOMAIN

CSRF_COOKIE_DOMAIN: str = env.COOKIE_DOMAIN
CSRF_TRUSTED_ORIGINS: list[str] = env.TRUSTED_ORIGINS

CORS_ALLOWED_ORIGINS: list[str] = env.TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS: bool = True