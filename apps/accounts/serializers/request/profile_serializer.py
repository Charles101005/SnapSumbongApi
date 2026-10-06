from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import Users
from apps.accounts.serializers.base_serializer import BasePasswordValidationSerializer
from external.storage import StorageService, UploadIntent


class ChangePasswordRequestSerializer(BasePasswordValidationSerializer):
    current_password = serializers.CharField(min_length=8)
    new_password = serializers.CharField(min_length=8)

    def validate_new_password(self, value):
        return self._validate_password_complexity(value)

    def validate(self, attrs):
        current_password = attrs.get("current_password")
        new_password = attrs.get("new_password")

        if current_password and new_password and new_password == current_password:
            raise serializers.ValidationError({
                "new_password": "Your new password cannot be the same as your current password."
            })

        return attrs


class UpdateProfileRequestSerializer(serializers.Serializer):
    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(max_length=50)
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use.",
        )]
    )
    contact_number = serializers.CharField(min_length=11, max_length=11)
    is_notified = serializers.BooleanField()
    profile_picture = serializers.URLField(max_length=500)

    def validate_profile_picture(self, value):
        expected_base_url = StorageService.get_expected_response_base_url()
        expected_folder = f"/{UploadIntent.USER_PROFILES.value}/"

        if not value.startswith(expected_base_url) or expected_folder not in value:
            raise serializers.ValidationError("Invalid URL")

        return value