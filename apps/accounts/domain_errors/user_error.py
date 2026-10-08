from rest_framework import status

from shared.results import DomainError


UserNotFoundError = DomainError(
    detail="No account was found with that email/user number.",
    status_code=status.HTTP_404_NOT_FOUND,
    error_code="USER_NOT_FOUND",
)

IncorrectAccountCredentialsError = DomainError(
    detail="Incorrect account credentials.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="INCORRECT_ACCOUNT_CREDENTIALS",
)

SelfUpdateDeniedError =  DomainError(
    detail="You cannot update your own account role or status.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="SELF_UPDATE_DENIED",
)
