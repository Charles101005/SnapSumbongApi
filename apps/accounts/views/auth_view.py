from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.middleware.csrf import rotate_token
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings

from apps.accounts.serializers.request.auth_serializer import LoginRequestSerializer
from apps.accounts.serializers.response.auth_serializer import CurrentUserResponseSerializer


def set_refresh_cookie(response: Response, refresh: str) -> None:
    refresh_lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
    cookie_max_age = int(refresh_lifetime.total_seconds())

    response.set_cookie(
        key='refresh',
        value=refresh,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        path='/accounts',
        max_age=cookie_max_age
    )


@method_decorator(ensure_csrf_cookie, name='dispatch')
class LoginView(TokenObtainPairView):
    serializer_class = LoginRequestSerializer

    def post(self, request: Request, *args, **kwargs) -> Response:
        rotate_token(request)

        response: Response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            refresh: str = response.data.pop('refresh')

            set_refresh_cookie(response, refresh)

        return response


@method_decorator(csrf_protect, name='dispatch')
class RefreshView(TokenRefreshView):
    def post(self, request: Request, *args, **kwargs) -> Response:
        refresh: str = request.COOKIES.get('refresh')

        serializer = self.get_serializer(
            data={'refresh': refresh},
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        response: Response = Response(
            data={'access': data['access']}
        )

        return response


@method_decorator(csrf_protect, name='dispatch')
class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        refresh: str = request.COOKIES.get('refresh')

        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass

        response: Response = Response(
            status=status.HTTP_204_NO_CONTENT,
        )

        response.delete_cookie(
            key='refresh',
            path='/accounts',
            samesite='Lax',
        )

        return response


class CurrentUserView(APIView):
    def get(self, request: Request) -> Response:
        serializer = CurrentUserResponseSerializer(request.user)

        return Response(data=serializer.data)