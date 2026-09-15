from rest_framework import serializers


class GetHazardCategoryListResponseSerializer(serializers.Serializer):
    hazard_id = serializers.IntegerField()
    hazard_name = serializers.CharField()
    description = serializers.CharField()