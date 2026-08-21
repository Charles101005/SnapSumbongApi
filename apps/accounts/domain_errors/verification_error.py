from rest_framework import status

from shared.results import DomainError


InvalidVerificationOTPError = DomainError(
    detail="The verification code you entered is invalid.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="INVALID_VERIFICATION_OTP",
)

VerificationExpiredError = DomainError(
    detail="This verification code has expired. Please request a new one.",
    status_code=status.HTTP_410_GONE,
    error_code="VERIFICATION_EXPIRED",
)

VerificationAttemptsExceededError = DomainError(
    detail="Maximum verification attempts exceeded. Please request a new code.",
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    error_code="VERIFICATION_ATTEMPTS_EXCEEDED",
)

OTPResendLimitExceededError = DomainError(
    detail="You have exceeded the maximum number of code requests. Please register again.",
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    error_code="OTP_RESEND_LIMIT_EXCEEDED",
)

OTPResendCooldownActiveError = DomainError(
    detail="Please wait a moment before requesting another verification code.",
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    error_code="OTP_RESEND_COOLDOWN_ACTIVE",
)

VerificationInProgressError = DomainError(
    detail="A verification code was already sent to this email address. Please check your inbox.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="VERIFICATION_IN_PROGRESS",
)