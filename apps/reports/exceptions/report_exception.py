from rest_framework import status

from shared.exceptions import BaseDomainException


class InvalidImageCountException(BaseDomainException):
    detail: str = "The requested image count is invalid"
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "INVALID_IMAGE_COUNT"


class InvalidHazardCategoryException(BaseDomainException):
    detail: str = "The provided hazard category are invalid"
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "INVALID_HAZARD_CATEGORY"


class ReportDoesNotExistException(BaseDomainException):
    detail: str = "The specified report does not exist"
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "REPORT_DOES_NOT_EXIST"
