from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.models import Users
from apps.accounts.exceptions.auth_exception import RefreshTokenMissingException, RefreshTokenInvalidException


class AuthService:
    @staticmethod
    def revoke_all_refresh_tokens(user: Users) -> None:
        tokens = OutstandingToken.objects.filter(user=user)

        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

    @staticmethod
    def revoke_other_refresh_tokens(
            *,
            user: Users,
            current_refresh_token: str,
    ) -> None:
        if not current_refresh_token:
            raise RefreshTokenMissingException()

        try:
            current_token = RefreshToken(current_refresh_token)
        except TokenError:
            raise RefreshTokenInvalidException()

        current_jti = current_token["jti"]

        tokens = OutstandingToken.objects.filter(user=user).exclude(jti=current_jti)

        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
