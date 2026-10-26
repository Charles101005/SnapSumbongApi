from rest_framework import serializers

from apps.accounts.models import Users
from apps.accounts.serializers.base_serializer import BasePasswordValidationSerializer
from apps.accounts.validators.serializer_validator import ten_digit_psgc_code_validator
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
    contact_number = serializers.CharField(min_length=11, max_length=11)
    is_notified = serializers.BooleanField()
    profile_picture = serializers.URLField(max_length=500)

    gender = serializers.ChoiceField(choices=Users.GenderChoices.choices)
    birth_date = serializers.DateField()

    # Address fields are optional (citizens may leave them empty) and
    # clearable: a blank/null value wipes the stored value. Real codes must
    # still be 10-digit PSGC — DRF skips field validators on empty values.
    street_address = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )

    region_code = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True,
        validators=[ten_digit_psgc_code_validator],
    )
    province_code = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True,
        validators=[ten_digit_psgc_code_validator],
    )
    city_code = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True,
        validators=[ten_digit_psgc_code_validator],
    )
    barangay_code = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True,
        validators=[ten_digit_psgc_code_validator],
    )

    def validate_street_address(self, value):
        return value or None

    def validate_region_code(self, value):
        return value or None

    def validate_province_code(self, value):
        return value or None

    def validate_city_code(self, value):
        return value or None

    def validate_barangay_code(self, value):
        return value or None

    def validate(self, attrs):
        if 'email' in self.initial_data:
            raise serializers.ValidationError({
                'email': 'Email changes must be verified. '
                         'Please use POST /profile/email-change/request/ to change your email address.'
            })
        return attrs

    def validate_profile_picture(self, value):
        expected_base_url = StorageService.get_expected_response_base_url()
        expected_folder = f"/{UploadIntent.USER_PROFILES.value}/"

        if not value.startswith(expected_base_url) or expected_folder not in value:
            raise serializers.ValidationError("Invalid URL")

        return value


class RequestEmailChangeRequestSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None

        if user:
            if value.lower() == user.email.lower():
                raise serializers.ValidationError(
                    "New email cannot be the same as your current email."
                )

            if Users.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
                raise serializers.ValidationError(
                    "The provided email address is already in use."
                )

        return value


class VerifyEmailChangeRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(write_only=True, min_length=4, max_length=4)


class ResendEmailChangeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()