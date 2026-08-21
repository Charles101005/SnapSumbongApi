from rest_framework import status

from shared.exceptions.base_exception import BaseDomainException


class SystemCitizenRoleMissingException(BaseDomainException):
    detail: str = 'The default (Citizen) system role was not found in the database.'
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = 'SYSTEM_CITIZEN_ROLE_MISSING'


class RoleNotFoundException(BaseDomainException):
    detail: str = 'The role id provided is invalid'
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = 'ROLE_NOT_FOUND'