from rest_framework import serializers


class CreateEmployeeResponseSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    email = serializers.EmailField()

    def get_full_name(self, obj) -> str:
        return obj.get_full_name()

    def get_role(self, obj) -> str:
        return obj.role.role_name


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
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            data.pop("role", None)

        return data


class UserDetailResponseSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField(default=None)
    email = serializers.EmailField()
    role = serializers.SerializerMethodField()
    role_id = serializers.IntegerField()

    is_active = serializers.BooleanField()

    last_active = serializers.DateTimeField()
    created_at = serializers.DateTimeField()

    def get_role(self, obj) -> str:
        return obj.role.role_name
