from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import Users


class CreateEmployeeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use."
        )],
    )
    role_id = serializers.IntegerField()

    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(required=False, max_length=50, default=None, allow_null=True, allow_blank=True)


class UserListRequestSerializer(serializers.Serializer):
    q = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    role_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            attrs.pop("role_id", None)

        return attrs


class UserUpdateRequestSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    role_id = serializers.IntegerField()

    def validate(self, attrs):
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            attrs.pop("role_id", None)

        return attrs
