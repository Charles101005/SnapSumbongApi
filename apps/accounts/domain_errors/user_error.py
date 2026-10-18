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

WarnTargetNotCitizenError = DomainError(
    detail="Warnings can only be issued to citizen accounts.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="WARN_TARGET_NOT_CITIZEN",
)

WarnTargetInactiveError = DomainError(
    detail="Warnings can only be issued to active accounts.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="WARN_TARGET_INACTIVE",
)

LinkedReportNotInvalidError = DomainError(
    detail="The linked report must be in Invalid status to be cited as evidence.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="LINKED_REPORT_NOT_INVALID",
)

LinkedReportNotOwnedError = DomainError(
    detail="The linked report does not belong to the target citizen.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="LINKED_REPORT_NOT_OWNED",
)

LinkedReportAlreadyWarnedError = DomainError(
    detail="A warning has already been issued for this report. Each report can only support one warning.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="LINKED_REPORT_ALREADY_WARNED",
)

BanTargetNotCitizenError = DomainError(
    detail="Bans can only be applied to citizen accounts.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="BAN_TARGET_NOT_CITIZEN",
)

BanTargetInactiveError = DomainError(
    detail="This account is already banned.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="BAN_TARGET_INACTIVE",
)

BanSelfDeniedError = DomainError(
    detail="You cannot ban your own account.",
    status_code=status.HTTP_403_FORBIDDEN,
    error_code="BAN_SELF_DENIED",
)

BanNotEligibleError = DomainError(
    detail="Ban not eligible: the citizen needs at least 3 warnings, or you must cite a specific Invalid report for fast-track ban.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="BAN_NOT_ELIGIBLE",
)

FastTrackReportNotInvalidError = DomainError(
    detail="The fast-track report must be in Invalid status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="FAST_TRACK_REPORT_NOT_INVALID",
)

FastTrackReportNotOwnedError = DomainError(
    detail="The fast-track report does not belong to the target citizen.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="FAST_TRACK_REPORT_NOT_OWNED",
)

UnbanTargetNotInactiveError = DomainError(
    detail="This account is not currently banned.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="UNBAN_TARGET_NOT_INACTIVE",
)

UnbanTargetNotCitizenError = DomainError(
    detail="Unbans can only be applied to citizen accounts.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="UNBAN_TARGET_NOT_CITIZEN",
)
