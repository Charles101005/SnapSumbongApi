from rest_framework import status


class DomainError:
    def __init__(
            self,
            detail: str,
            status_code: int = status.HTTP_400_BAD_REQUEST,
            error_code: str = "DOMAIN_ERROR",
    ) -> None:
        self.detail: str = detail
        self.status_code: int = status_code
        self.error_code: str = error_code.upper()

    def with_meta(self, meta: dict) -> 'DomainErrorWithMeta':
        return DomainErrorWithMeta(self, meta)


class DomainErrorWithMeta:
    def __init__(
            self,
            domain_error: DomainError,
            meta: dict,
    ) -> None:
        self.detail: str = domain_error.detail
        self.status_code: int = domain_error.status_code
        self.error_code: str = domain_error.error_code
        self.meta: dict = meta

