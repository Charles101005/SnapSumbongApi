from rest_framework import serializers


class UserListResponseSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField()
    role = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    last_active = serializers.DateTimeField()

    def get_full_name(self, obj) -> str:
        return obj.get_full_name()

    def get_role (self, obj) -> str:
        return obj.role.role_name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        list_staff: bool= self.context.get("list_staff")

        if not list_staff:
            data.pop("role", None)

        return data
