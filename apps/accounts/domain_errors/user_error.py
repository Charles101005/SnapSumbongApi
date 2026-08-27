from rest_framework import status

from shared.results import DomainError


UserNotFoundError = DomainError(
    detail="No account was found with that email address.",
    status_code=status.HTTP_404_NOT_FOUND,
    error_code="USER_NOT_FOUND",
)