from rest_framework import status

from shared.results import DomainError


DuplicateStatusTransitionError = DomainError(
    detail="The report is already in the specified status. No update was performed.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="DUPLICATE_STATUS_TRANSITION",
)

InvalidReportUpdateError = DomainError(
    detail="Remarks or resolution images can only come with a status change.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="INVALID_REPORT_UPDATE",
)

StatusResolutionImageConflictError = DomainError(
    detail="Resolution images can only be uploaded when transitioning to resolved status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="STATUS_RESOLUTION_IMAGE_CONFLICT",
)

ResolutionImageRequiredError = DomainError(
    detail="Resolution images are required when transitioning to resolved status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="RESOLUTION_IMAGE_REQUIRED",
)

MissingDuringPhotoError = DomainError(
    detail="The photolog requires at least one 'During' photo of the rectification works.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MISSING_DURING_PHOTO",
)

MissingAfterPhotoError = DomainError(
    detail="The photolog requires at least one 'After' photo of the completed rectification.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MISSING_AFTER_PHOTO",
)

MandatoryRemarksStatusError = DomainError(
    detail="A detailed remark is required when moving a report to this status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MANDATORY_REMARKS_STATUS",
)

AssignedStatusTransitionError = DomainError(
    detail="An Assigned report can only move to Under Review.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="ASSIGNED_STATUS_TRANSITION",
)

MandatorySeverityStatusError = DomainError(
    detail="A severity (P1-P5) is required when moving a report out of Under Review to On-Hold or Dispatched.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MANDATORY_SEVERITY_STATUS",
)

CategoryChangeNotPermittedError = DomainError(
    detail="The hazard category can only be changed while the report is Under Review.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="CATEGORY_CHANGE_NOT_PERMITTED",
)

MandatoryCategoryRemarksError = DomainError(
    detail="A detailed remark is required when changing the hazard category.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MANDATORY_CATEGORY_REMARKS",
)

ReportNotResolvedError = DomainError(
    detail="Only reports with resolved status can be confirmed by the reporter.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="CONFIRMATION_NOT_RESOLVED",
)

ValidatorNameRequiredError = DomainError(
    detail="The name of the validator is required when transitioning to resolved status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="VALIDATOR_NAME_REQUIRED",
)

ReportNotTransferableError = DomainError(
    detail="Only open reports can be transferred. This report has already been resolved or closed.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="REPORT_NOT_TRANSFERABLE",
)

InvalidTransferTargetError = DomainError(
    detail="The selected account is not an active officer eligible to handle reports.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="INVALID_TRANSFER_TARGET",
)

AlreadyAssignedToTargetError = DomainError(
    detail="The report is already assigned to the selected officer.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="ALREADY_ASSIGNED_TO_TARGET",
)
