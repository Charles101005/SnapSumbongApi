from rest_framework import serializers


class VerifyRegistrationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    access = serializers.SerializerMethodField()

    def get_access(self, obj) -> str | None:
        return self.context.get('access')
