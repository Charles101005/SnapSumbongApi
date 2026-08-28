from rest_framework import serializers


class VerifyForgotPasswordResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()


class ResetPasswordResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()