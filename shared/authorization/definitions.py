from dataclasses import dataclass

@dataclass(frozen=True)
class PermissionDefinition:
    name: str
    description: str
    module: str


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    code: str
    description: str
    is_protected: bool
    permissions: tuple[PermissionDefinition, ...]
    mandatory_permissions: tuple[str, ...] = tuple()
