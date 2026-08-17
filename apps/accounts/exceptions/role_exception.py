from rest_framework import status

from shared.exceptions.base_exception import BaseDomainException


class DefaultCitizenRoleNotFoundError(BaseDomainException):
    detail: str = 'The default (Citizen) system role was not found in the database.'
    status: int = status.HTTP_500_INTERNAL_SERVER_ERROR


class RoleNotFoundError(BaseDomainException):
    detail: str = 'The role id provided is invalid'
    status: int = status.HTTP_400_BAD_REQUEST