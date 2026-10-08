from rest_framework import serializers


class ListRolesResponseSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()
    is_protected = serializers.BooleanField()
    permissions = serializers.SerializerMethodField()

    def get_permissions(self, obj) -> list[str]:
        return list(obj.permissions.values_list("permission_name", flat=True))


class DetailRoleResponseSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()
    description = serializers.CharField()
    is_protected = serializers.BooleanField()
    permissions = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_permissions(self, obj) -> list[str]:
        return list(obj.permissions.values_list("permission_name", flat=True))
