from rest_framework import status

from shared.results import DomainError


EmailSameAsCurrentError = DomainError(
    detail="New email cannot be the same as your current email.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="EMAIL_SAME_AS_CURRENT",
)

EmailAlreadyTakenError = DomainError(
    detail="The provided email address is already in use.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="EMAIL_ALREADY_TAKEN",
)

EmailChangeVerificationInvalidError = DomainError(
    detail="Invalid or expired email change verification request.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="EMAIL_CHANGE_VERIFICATION_INVALID",
)
