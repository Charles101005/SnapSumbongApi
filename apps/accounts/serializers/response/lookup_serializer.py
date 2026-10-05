from rest_framework import serializers


class LookupRolesResponseSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()