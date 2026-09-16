from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import Users
from apps.accounts.serializers.base_serializer import BasePasswordValidationSerializer


class RegistrationRequestSerializer(BasePasswordValidationSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use."
        )],
    )
    password = serializers.CharField(write_only=True, min_length=8)

    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(required=False, max_length=50, default=None, allow_null=True, allow_blank=True)


    def validate_password(self, value):
        return self._validate_password_complexity(value)
