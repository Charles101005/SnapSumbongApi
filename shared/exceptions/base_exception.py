from rest_framework import status


class BaseDomainException(Exception):
    detail: str = "An error occurred while handling your request."
    status: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str|None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)