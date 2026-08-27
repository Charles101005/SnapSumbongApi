from rest_framework import serializers


class ForgotPasswordResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()


class VerifyForgotPasswordResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()


class ResendForgotPasswordVerificationCodeResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()


class ResetPasswordResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()