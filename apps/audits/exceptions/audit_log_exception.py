from rest_framework import status

from shared.exceptions import BaseDomainException


class AuditLogNotFoundException(BaseDomainException):
    detail: str = "The audit log provided does not exist."
    status_code: int = status.HTTP_404_NOT_FOUND
    error_code: str = "AUDIT_LOG_NOT_FOUND"