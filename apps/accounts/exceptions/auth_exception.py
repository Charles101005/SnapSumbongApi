from rest_framework import status

from shared.exceptions import BaseDomainException


class RefreshTokenMissingException(BaseDomainException):
    detail: str = "Refresh token is required."
    status_code: int = status.HTTP_401_UNAUTHORIZED
    error_code: str = "REFRESH_TOKEN_MISSING"


class RefreshTokenInvalidException(BaseDomainException):
    detail: str = "Invalid refresh token."
    status_code: int = status.HTTP_401_UNAUTHORIZED
    error_code: str = "REFRESH_TOKEN_INVALID"