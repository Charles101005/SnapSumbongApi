from rest_framework import serializers


class CreateEmployeeResponseSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    full_name = serializers.CharField(source='get_full_name')
    role = serializers.CharField(source='role.role_name')
    email = serializers.EmailField()


class UserListResponseSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    full_name = serializers.CharField(source='get_full_name')
    email = serializers.EmailField()
    role = serializers.CharField(source='role.role_name')
    is_active = serializers.BooleanField()
    last_active = serializers.DateTimeField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        is_staff: bool = self.context.get("is_staff")

        if not is_staff:
            data.pop("role", None)

        return data


class UserDetailResponseSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField(default=None)
    email = serializers.EmailField()

    gender = serializers.CharField(source="get_gender_display", default=None)
    profile_picture = serializers.URLField(default=None)
    contact_number = serializers.CharField(default=None)
    birth_date = serializers.DateField(default=None)
    street_address = serializers.CharField(max_length=255, default=None)

    region_code = serializers.CharField(default=None)
    province_code = serializers.CharField(default=None)
    city_code = serializers.CharField(default=None)
    barangay_code = serializers.CharField(default=None)

    role = serializers.CharField(source="role.role_name")
    role_id = serializers.IntegerField()

    is_active = serializers.BooleanField()

    last_active = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
