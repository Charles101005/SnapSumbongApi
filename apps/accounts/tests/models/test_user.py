import pytest
from django.db import IntegrityError

from apps.accounts.tests.factories import UserFactory
from apps.accounts.models import Users


STATIC_EMAIL = 'test@email.com'

@pytest.mark.django_db
class TestUserModel:
    email = STATIC_EMAIL

    def test_unique_email_constraint(self, citizen_role):
        UserFactory(
            email=self.email,
            role=citizen_role,
        )
        with pytest.raises(IntegrityError):
            UserFactory(
                email=self.email,
                role=citizen_role,
            )

    def test_model_str(self, citizen_role):
        test_user = UserFactory(role=citizen_role)
        assert str(test_user) == test_user.email


@pytest.mark.django_db
class TestUserManager:
    email = STATIC_EMAIL
    first_name = 'John'
    last_name = 'Doe'
    middle_name = 'Jane'
    password = 'Password2005'

    @pytest.mark.parametrize(
        "extra_kwargs, expected_is_active, is_check_password",
        [
            #1. Test if raw password gets hashed
            ({"password": password}, True, True),
            #2. Test if pre-hashed password gets saved as is
            ({"password_hash": password}, True, False),
            #3. Test if extra fields passes through
            ({"password": password, "is_active": False}, False, True),
        ]
    )
    def test_create_user_variants(self, citizen_role, extra_kwargs, expected_is_active, is_check_password):
        base_kwargs = {
            'email': self.email,
            'role': citizen_role,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'middle_name': self.middle_name,
        }
        full_kwargs = {**base_kwargs, **extra_kwargs}
        Users.objects.create_user(**full_kwargs)

        user = Users.objects.get(email=self.email)

        assert user is not None
        assert user.email == self.email
        assert user.first_name == self.first_name
        assert user.last_name == self.last_name
        assert user.middle_name == self.middle_name
        assert user.is_active == expected_is_active

        if is_check_password:
            assert user.check_password(self.password)
        else:
            assert user.password == self.password

    @pytest.mark.parametrize(
        "extra_kwargs",
        [
            # 1. Test with no password and password_hash provided
            ({}),
            # 2. Test with password and password_hash provided
            ({"password": password, "password_hash": password}),
        ]
    )
    def test_create_user_password_check_variants(self, citizen_role, extra_kwargs):
        with pytest.raises(ValueError, match='Provide only one password type'):
            Users.objects.create_user(
                email=self.email,
                role=citizen_role,
                first_name=self.first_name,
                last_name=self.last_name,
                middle_name=self.middle_name,
                **extra_kwargs
            )

    def test_get_by_active_email_or_none_when_active(self, citizen_role):
        test_user: Users = UserFactory(role=citizen_role)

        user = Users.objects.get_by_active_email_or_none(test_user.email)

        assert user is not None
        assert user.email == test_user.email
        assert user.first_name == test_user.first_name
        assert user.last_name == test_user.last_name
        assert user.middle_name == test_user.middle_name
        assert user.is_active == True

    def test_get_by_active_email_or_none_when_not_active(self, citizen_role):
        test_user: Users = UserFactory(
            role=citizen_role,
            is_active=False
        )

        user = Users.objects.get_by_active_email_or_none(test_user.email)

        assert user is None
