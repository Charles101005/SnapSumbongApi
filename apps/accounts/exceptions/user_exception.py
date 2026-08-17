from rest_framework import status

from shared.exceptions.base_exception import BaseDomainException


class UserAlreadyExistsError(BaseDomainException):
    detail: str = "The provided user email already exists."
    status: int = status.HTTP_400_BAD_REQUEST