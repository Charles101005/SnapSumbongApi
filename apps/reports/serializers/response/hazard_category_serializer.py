from rest_framework import serializers


class GetHazardCategoryListSerializer(serializers.Serializer):
    hazard_id = serializers.IntegerField()
    hazard_name = serializers.CharField()
    description = serializers.CharField()