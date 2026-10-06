from rest_framework import status

from shared.results import DomainError


MetricsNotApplicableToRoleError = DomainError(
    detail="The role of the specified user number is not applicable to have these metrics.",
    status_code=status.HTTP_409_CONFLICT,
    error_code="METRICS_NOT_APPLICABLE_TO_ROLE",
)