from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from .domain_result import DomainResult


class DomainResultResponse:
    def __init__(self, result: DomainResult) -> None:
        self._result = result

    def _handle_error(self) -> Response:
        error_obj = self._result.error

        return Response(
            data={
                "detail": error_obj.detail,
                "error_code": error_obj.error_code,
                "meta": getattr(error_obj, "meta", {}),
            },
            status=error_obj.status_code,
        )

    def respond(
            self,
            *,
            serializer_class: type[Serializer]=None,
            success_status_code: int = status.HTTP_200_OK,
            serializer_context: dict[str, Any]=None,
    ) -> Response:
        if not self._result.is_success:
            return self._handle_error()

        if serializer_class:
            context = serializer_context or {}
            data = serializer_class(self._result.value, context=context).data
        else:
            data = self._result.value

        return Response(data=data, status=success_status_code)

    def respond_with_pagination(self):
        pass