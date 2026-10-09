from rest_framework import serializers


class CreateUpdateRoleRequestSerializer(serializers.Serializer):
    role_name = serializers.CharField()
    description = serializers.CharField()
    permission_names = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
    )
