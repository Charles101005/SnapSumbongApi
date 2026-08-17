from rest_framework.views import exception_handler
from rest_framework.response import Response

from .base_exception import BaseDomainException


def global_exception_handler(exc: Exception, context: dict) -> Response|None:
    response: Response|None = exception_handler(exc, context)

    if response is not None:
        return response

    if isinstance(exc, BaseDomainException):
        return Response(
            data={"detail": exc.detail},
            status=exc.status
        )

    return None