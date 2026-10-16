import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.exceptions.auth_exception import (
    RefreshTokenInvalidException,
    RefreshTokenMissingException,
)
from apps.accounts.services import AuthService
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestRevokeAllRefreshTokens:
    def test_blacklists_every_outstanding_token_for_user(self, citizen_role):
        user = UserFactory(role=citizen_role)
        first_token = RefreshToken.for_user(user)
        second_token = RefreshToken.for_user(user)

        AuthService.revoke_all_refresh_tokens(user=user)

        assert BlacklistedToken.objects.filter(token__token=str(first_token)).exists()
        assert BlacklistedToken.objects.filter(token__token=str(second_token)).exists()

    def test_does_not_affect_other_users_tokens(self, citizen_role):
        user = UserFactory(role=citizen_role)
        other_user = UserFactory(role=citizen_role)
        other_token = RefreshToken.for_user(other_user)

        AuthService.revoke_all_refresh_tokens(user=user)

        assert not BlacklistedToken.objects.filter(token__token=str(other_token)).exists()


@pytest.mark.django_db
class TestRevokeOtherRefreshTokens:
    def test_raises_when_current_refresh_token_missing(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(RefreshTokenMissingException):
            AuthService.revoke_other_refresh_tokens(user=user, current_refresh_token='')

    def test_raises_when_current_refresh_token_invalid(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(RefreshTokenInvalidException):
            AuthService.revoke_other_refresh_tokens(user=user, current_refresh_token='not-a-jwt')

    def test_blacklists_all_except_current(self, citizen_role):
        user = UserFactory(role=citizen_role)
        current_token = RefreshToken.for_user(user)
        other_token = RefreshToken.for_user(user)

        AuthService.revoke_other_refresh_tokens(
            user=user,
            current_refresh_token=str(current_token),
        )

        assert BlacklistedToken.objects.filter(token__token=str(other_token)).exists()
        assert not BlacklistedToken.objects.filter(token__token=str(current_token)).exists()

    def test_leaves_other_users_tokens_untouched(self, citizen_role):
        user = UserFactory(role=citizen_role)
        other_user = UserFactory(role=citizen_role)
        current_token = RefreshToken.for_user(user)
        other_user_token = RefreshToken.for_user(other_user)

        AuthService.revoke_other_refresh_tokens(
            user=user,
            current_refresh_token=str(current_token),
        )

        assert not BlacklistedToken.objects.filter(token__token=str(other_user_token)).exists()

    def test_handles_user_with_single_token(self, citizen_role):
        user = UserFactory(role=citizen_role)
        current_token = RefreshToken.for_user(user)

        AuthService.revoke_other_refresh_tokens(
            user=user,
            current_refresh_token=str(current_token),
        )

        outstanding_count = OutstandingToken.objects.filter(user=user).count()
        assert outstanding_count == 1
        assert not BlacklistedToken.objects.filter(token__token=str(current_token)).exists()
