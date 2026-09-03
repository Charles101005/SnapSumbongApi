from rest_framework import status

from shared.exceptions import BaseDomainException


class VerificationNotFoundException(BaseDomainException):
    detail: str = "No active verification session was found."
    status_code: int = status.HTTP_404_NOT_FOUND
    error_code: str = "VERIFICATION_NOT_FOUND"