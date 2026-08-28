from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class BasePasswordValidationSerializer(serializers.Serializer):

    def _validate_password_complexity(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        return value