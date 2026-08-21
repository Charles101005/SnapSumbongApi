from rest_framework import status


class BaseDomainException(Exception):
    detail: str = "An unexpected system error occurred. Please try again later."
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "DOMAIN_EXCEPTION"

    def __init__(self, detail: str|None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)