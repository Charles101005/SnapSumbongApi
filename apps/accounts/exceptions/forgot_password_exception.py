from rest_framework import status

from shared.exceptions.base_exception import BaseDomainException


class ForgotPasswordRequestNotFoundException(BaseDomainException):
    detail: str = "Invalid or expired password reset request."
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "PASSWORD_RESET_INVALID"