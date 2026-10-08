from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import Users
from apps.accounts.validators.serializer_validator import ten_digit_psgc_code_validator


class CreateEmployeeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use."
        )],
    )
    role_id = serializers.IntegerField()

    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(required=False, max_length=50, default=None, allow_null=True, allow_blank=True)
    contact_number = serializers.CharField(min_length=11, max_length=11)
    birth_date = serializers.DateField()
    gender = serializers.ChoiceField(choices=Users.GenderChoices.choices)
    street_address = serializers.CharField(max_length=255)
    region_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    province_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    city_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    barangay_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])


class UserListRequestSerializer(serializers.Serializer):
    q = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    role_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            attrs.pop("role_id", None)

        return attrs


class UserUpdateRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=Users.objects.all(),
            message="The provided email address is already in use."
        )],
    )
    role_id = serializers.IntegerField()

    last_name = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=50)
    middle_name = serializers.CharField(required=False, max_length=50, default=None, allow_null=True, allow_blank=True)
    contact_number = serializers.CharField(min_length=11, max_length=11)
    birth_date = serializers.DateField()
    gender = serializers.ChoiceField(choices=Users.GenderChoices.choices)
    street_address = serializers.CharField(max_length=255)
    region_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    province_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    city_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])
    barangay_code = serializers.CharField(validators=[ten_digit_psgc_code_validator])

    is_active = serializers.BooleanField()

    def validate(self, attrs):
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            attrs.pop("email", None)
            attrs.pop("role_id", None)
            attrs.pop("last_name", None)
            attrs.pop("first_name", None)
            attrs.pop("middle_name", None)
            attrs.pop("contact_number", None)
            attrs.pop("birth_date", None)
            attrs.pop("gender", None)
            attrs.pop("street_address", None)
            attrs.pop("region_code", None)
            attrs.pop("province_code", None)
            attrs.pop("city_code", None)
            attrs.pop("barangay_code", None)

        return attrs
