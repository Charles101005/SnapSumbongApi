from rest_framework import status

from shared.results import DomainError


PasswordResetInvalidError = DomainError(
    detail="Invalid or expired password reset request.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="PASSWORD_RESET_INVALID",
)
