from rest_framework import serializers


class VerificationSessionCreationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()