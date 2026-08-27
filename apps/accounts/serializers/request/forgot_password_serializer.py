from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(write_only=True, min_length=4, max_length=4)


class ResendForgotPasswordVerificationCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        return value