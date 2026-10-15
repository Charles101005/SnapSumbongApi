from rest_framework import serializers


class WarnCitizenRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=500)
    report_number = serializers.CharField(required=False, allow_blank=True, default=None)


class BanCitizenRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=500)
    report_number = serializers.CharField(required=False, allow_blank=True, default=None)


class UnbanCitizenRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=500)
