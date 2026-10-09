from rest_framework import status

from shared.results import DomainError


RoleAlreadyExistError = DomainError(
    detail="The role with the given name already exists.",
    status_code=status.HTTP_400_BAD_REQUEST,
    error_code="ROLE_ALREADY_EXISTS",
)

PermissionNotFoundError = DomainError(
    detail="The permission with the given name does not exist.",
    status_code=status.HTTP_404_NOT_FOUND,
    error_code="PERMISSION_NOT_FOUND",
)
