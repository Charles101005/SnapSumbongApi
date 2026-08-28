from rest_framework import serializers


class VerifyOTPCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(write_only=True, min_length=4, max_length=4)


class ResendOTPCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()