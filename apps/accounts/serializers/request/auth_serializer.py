from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Users


class LoginRequestSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[self.username_field] = serializers.EmailField()
        self.fields['password'] = serializers.CharField(write_only=True, min_length=8)


    def validate(self, attrs):
        data: dict = super().validate(attrs)
        user: Users = self.user

        user_perms = list(user.role.permissions.values_list('permission_name', flat=True))

        data['user'] = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'middle_name': user.middle_name,
            'role': user.role.role_name,
            'is_staff': user.is_staff,
            'permissions': user_perms,
        }

        return data


