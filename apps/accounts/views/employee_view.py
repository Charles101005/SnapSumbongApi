from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from shared.results import DomainResultResponse


class EmployeeListView(APIView):
    def get(self, request: Request) -> Response:
        pass

    def post(self, request: Request) -> Response:
        pass


class EmployeeDetailView(APIView):
    def get(self, request: Request, user_number: str) -> Response:
        pass

    def patch(self, request: Request, user_number: str) -> Response:
        pass
