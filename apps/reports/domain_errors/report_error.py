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

MandatoryRemarksStatusError = DomainError(
    detail="A detailed remark is required when moving a report to this status.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="MANDATORY_REMARKS_STATUS",
)
