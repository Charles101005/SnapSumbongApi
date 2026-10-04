from rest_framework import serializers


class LookupRolesResponseSerializer(serializers.Serializer):
    role_code = serializers.CharField()
    role_name = serializers.CharField()