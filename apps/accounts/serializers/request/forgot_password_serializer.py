from rest_framework import serializers

from apps.accounts.serializers.base_serializer import BasePasswordValidationSerializer


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordRequestSerializer(BasePasswordValidationSerializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        return self._validate_password_complexity(value)