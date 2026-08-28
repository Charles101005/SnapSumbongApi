from rest_framework import serializers


class VerifyRegistrationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
