from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import Users


class RegistrationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use."
        )],
    )
    password = serializers.CharField(write_only=True)

    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(required=False, max_length=50, default=None, allow_null=True, allow_blank=True)


    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        return value


class VerifyRegistrationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(write_only=True, min_length=4, max_length=4)


class ResendVerificationCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()