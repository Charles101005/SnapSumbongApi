from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

from apps.reports.services import HazardCategoryService
from shared.results import DomainResultResponse
from apps.reports.serializers.response.hazard_category_serializer import GetHazardCategoryListResponseSerializer


class HazardCategoryListView(APIView):

    def get(self, request: Request) -> Response:
        result = HazardCategoryService.get_all_category()

        return DomainResultResponse(result).respond(
            serializer_class=GetHazardCategoryListResponseSerializer,
            success_status_code=status.HTTP_200_OK,
            serializer_is_many=True
        )

