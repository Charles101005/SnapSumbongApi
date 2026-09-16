from rest_framework import serializers

from apps.accounts.models import Users


class CurrentUserResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(max_length=50, default=None)
    role = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField()
    permissions = serializers.SerializerMethodField()

    def get_role(self, obj: Users) -> str:
        return obj.role.role_name

    def get_permissions(self, obj: Users) -> list[str]:
        return list(
            obj.role.permissions.values_list('permission_name', flat=True)
        )