from rest_framework import serializers


class CreateUpdateRoleRequestSerializer(serializers.Serializer):
    role_name = serializers.CharField()
    description = serializers.CharField()
    permission_names = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
    )


class ListRolesRequestSerializer(serializers.Serializer):
    q = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
