from rest_framework import serializers


class RegistrationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()


class VerifyRegistrationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResendVerificationCodeResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()