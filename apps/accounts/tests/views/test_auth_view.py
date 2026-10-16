import pytest
from django.conf import settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory, TEST_PASSWORD


LOGIN_URL = '/accounts/auth/login/'
REFRESH_URL = '/accounts/auth/refresh/'
LOGOUT_URL = '/accounts/auth/logout/'
CURRENT_USER_URL = '/accounts/auth/user/'


@pytest.mark.django_db
class TestLoginView:
    def test_successful_login_returns_access_and_sets_refresh_cookie(
            self,
            api_client,
            citizen_role,
    ):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': TEST_PASSWORD})

        assert response.status_code == 200
        data = response.json()
        assert 'access' in data
        assert 'refresh' not in data
        assert data['user']['email'] == user.email
        assert data['user']['role'] == citizen_role.role_name
        assert data['user']['is_staff'] is False
        assert 'user:read_own' in data['user']['permissions']

    def test_refresh_token_is_set_as_httponly_cookie(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': TEST_PASSWORD})

        refresh_cookie = response.cookies['refresh']
        assert refresh_cookie.value
        assert refresh_cookie['httponly']
        assert refresh_cookie['path'] == '/accounts'
        assert refresh_cookie['samesite'] == 'Lax'
        expected_max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
        assert int(refresh_cookie['max-age']) == expected_max_age

    def test_secure_flag_matches_debug_setting(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': TEST_PASSWORD})

        refresh_cookie = response.cookies['refresh']
        assert bool(refresh_cookie['secure']) is (not settings.DEBUG)

    def test_csrf_cookie_is_ensured(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': TEST_PASSWORD})

        assert 'csrftoken' in response.cookies

    def test_wrong_password_returns_401(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': 'WrongPassword1'})

        assert response.status_code == 401

    def test_unknown_email_returns_401(self, api_client):
        response = api_client.post(
            LOGIN_URL,
            {'email': 'unknown@email.com', 'password': TEST_PASSWORD},
        )

        assert response.status_code == 401

    def test_short_password_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(LOGIN_URL, {'email': user.email, 'password': 'short'})

        assert response.status_code == 400


@pytest.mark.django_db
class TestRefreshView:
    def test_valid_refresh_cookie_returns_access(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        refresh_token = RefreshToken.for_user(user)
        api_client.cookies['refresh'] = str(refresh_token)

        response = api_client.post(REFRESH_URL)

        assert response.status_code == 200
        data = response.json()
        assert 'access' in data
        assert 'refresh' not in data

    def test_missing_refresh_cookie_returns_401(self, api_client):
        response = api_client.post(REFRESH_URL)

        assert response.status_code == 401
        assert response.json()['detail'] == 'Invalid/expired refresh token'

    def test_invalid_refresh_cookie_returns_401(self, api_client):
        api_client.cookies['refresh'] = 'not-a-valid-token'

        response = api_client.post(REFRESH_URL)

        assert response.status_code == 401
        assert response.json()['detail'] == 'Invalid/expired refresh token'

    def test_blacklisted_refresh_token_returns_401(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        refresh_token = RefreshToken.for_user(user)
        outstanding_token = OutstandingToken.objects.get(token=str(refresh_token))
        BlacklistedToken.objects.create(token=outstanding_token)
        api_client.cookies['refresh'] = str(refresh_token)

        response = api_client.post(REFRESH_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_blacklists_token_and_deletes_cookie(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        refresh_token = RefreshToken.for_user(user)
        api_client.cookies['refresh'] = str(refresh_token)
        api_client.force_authenticate(user=user)

        response = api_client.post(LOGOUT_URL)

        assert response.status_code == 204
        assert response.cookies['refresh'].value == ''
        assert BlacklistedToken.objects.filter(token__token=str(refresh_token)).exists()

    def test_logout_without_cookie_still_succeeds(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(LOGOUT_URL)

        assert response.status_code == 204

    def test_logout_with_invalid_token_still_succeeds(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.cookies['refresh'] = 'not-a-valid-token'
        api_client.force_authenticate(user=user)

        response = api_client.post(LOGOUT_URL)

        assert response.status_code == 204

    def test_logout_unauthenticated_returns_401(self, api_client):
        response = api_client.post(LOGOUT_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestCurrentUserView:
    def test_returns_current_user_with_role_and_permissions(
            self,
            api_client,
            citizen_role,
    ):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(CURRENT_USER_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == user.email
        assert data['first_name'] == user.first_name
        assert data['role'] == citizen_role.role_name
        assert data['is_staff'] is False
        assert 'user:read_own' in data['permissions']

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(CURRENT_USER_URL)

        assert response.status_code == 401
