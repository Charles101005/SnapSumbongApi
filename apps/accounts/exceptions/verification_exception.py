from rest_framework import status

from shared.exceptions.base_exception import BaseDomainException


class InvalidVerificationOTPError(BaseDomainException):
    detail: str = "The verification code you entered is incorrect."
    status: int = status.HTTP_400_BAD_REQUEST


class VerificationExpiredError(BaseDomainException):
    detail: str = "This verification code has expired. Please request a new one."
    status: int = status.HTTP_410_GONE


class VerificationAttemptsExceededError(BaseDomainException):
    detail: str = "Maximum verification attempts exceeded. Please request a new code."
    status: int = status.HTTP_429_TOO_MANY_REQUESTS


class OTPResendLimitExceededError(BaseDomainException):
    detail: str = "You have exceeded the maximum number of code requests. Please register again."
    status: int = status.HTTP_429_TOO_MANY_REQUESTS


class OTPResendCooldownActiveError(BaseDomainException):
    detail: str = "Please wait a moment before requesting another verification code."
    status: int = status.HTTP_429_TOO_MANY_REQUESTS


class VerificationNotFoundError(BaseDomainException):
    detail: str = "No active verification session was found."
    status: int = status.HTTP_404_NOT_FOUND