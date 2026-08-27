from .base_domain_error import DomainError, DomainErrorWithMeta


class DomainResult[T]:
    def __init__(
            self,
            is_success: bool,
            value: T|None = None,
            error: DomainError|DomainErrorWithMeta|None = None,
    ) -> None:
        self.is_success = is_success
        self.value = value
        self.error = error

    @classmethod
    def success(cls, value: T = None):
        return cls(is_success=True, value=value)

    @classmethod
    def error(cls, error: DomainError|DomainErrorWithMeta):
        return cls(is_success=False, error=error)

    def unwrap(self) -> tuple[T|None, DomainError|DomainErrorWithMeta|None]:
        return self.value, self.error