import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import RoleFactory, UserFactory, TEST_PASSWORD
from external.storage import StorageService, UploadIntent


PROFILE_URL = '/accounts/profile/'
CHANGE_PASSWORD_URL = '/accounts/profile/change-password/'
DEACTIVATE_URL = '/accounts/profile/deactivate/'
IMAGE_SIGNATURE_URL = '/accounts/profile/image-signature/'


def _valid_profile_payload(user, **overrides):
    base_url = StorageService.get_expected_response_base_url()
    payload = {
        'last_name': 'Dela Cruz',
        'first_name': 'Juan',
        'middle_name': 'Santos',
        'contact_number': '09171234567',
        'is_notified': False,
        'profile_picture': f'{base_url}{UploadIntent.USER_PROFILES.value}/abc123_pfp.jpg',
        'gender': 'M',
        'birth_date': '1995-01-01',
        'street_address': '123 Rizal St',
        'region_code': '1300000000',
        'province_code': '1339000000',
        'city_code': '1339000000',
        'barangay_code': '1339010000',
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestProfileView:
    def test_get_profile_returns_own_data(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(PROFILE_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == user.email
        assert data['first_name'] == user.first_name
        assert data['is_notified'] is True

    def test_unauthenticated_get_returns_401(self, api_client):
        response = api_client.get(PROFILE_URL)

        assert response.status_code == 401

    def test_patch_updates_profile(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        original_email = user.email
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, first_name='Updated'),
            format='json',
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_name == 'Updated'
        assert user.email == original_email  # email unchanged
        assert user.contact_number == '09171234567'
        assert user.is_notified is False

    def test_patch_with_email_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, email='changed@email.com'),
            format='json',
        )

        assert response.status_code == 400
        assert 'email' in response.json()

    def test_patch_with_own_email_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, email=user.email),
            format='json',
        )

        assert response.status_code == 400
        assert 'email' in response.json()

    def test_patch_invalid_profile_picture_url_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, profile_picture='https://example.com/evil.jpg'),
            format='json',
        )

        assert response.status_code == 400
        assert 'profile_picture' in response.json()

    def test_patch_invalid_psgc_code_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, city_code='123'),
            format='json',
        )

        assert response.status_code == 400
        assert 'city_code' in response.json()

    def test_patch_invalid_gender_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            PROFILE_URL,
            _valid_profile_payload(user, gender='X'),
            format='json',
        )

        assert response.status_code == 400
        assert 'gender' in response.json()


@pytest.mark.django_db
class TestChangePasswordView:
    def test_correct_current_password_succeeds(self, api_client, citizen_role, mocker):
        revoke_mock = mocker.patch(
            'apps.accounts.services.user_service.AuthService.revoke_other_refresh_tokens',
        )
        user = UserFactory(role=citizen_role)
        refresh_token = RefreshToken.for_user(user)
        api_client.cookies['refresh'] = str(refresh_token)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {'current_password': TEST_PASSWORD, 'new_password': 'NewPassword123!'},
            format='json',
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password('NewPassword123!')
        revoke_mock.assert_called_once()

    def test_wrong_current_password_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {'current_password': 'WrongPassword1', 'new_password': 'NewPassword123!'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'INCORRECT_ACCOUNT_CREDENTIALS'
        user.refresh_from_db()
        assert user.check_password(TEST_PASSWORD)

    def test_same_new_password_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        user.set_password('Passw0rd!')
        user.save(update_fields=['password'])
        api_client.force_authenticate(user=user)

        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {'current_password': 'Passw0rd!', 'new_password': 'Passw0rd!'},
            format='json',
        )

        assert response.status_code == 400
        assert 'new_password' in response.json()

    def test_weak_new_password_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {'current_password': TEST_PASSWORD, 'new_password': 'password'},
            format='json',
        )

        assert response.status_code == 400
        assert 'new_password' in response.json()

    def test_permission_denied_without_update_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {'current_password': TEST_PASSWORD, 'new_password': 'NewPassword123'},
            format='json',
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestDeactivateAccountView:
    def test_deactivates_own_account(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(DEACTIVATE_URL)

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_active is False

    def test_permission_denied_without_deactivate_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(DEACTIVATE_URL)

        assert response.status_code == 403


@pytest.mark.django_db
class TestProfileImageSignatureView:
    def test_returns_upload_signature(self, api_client, citizen_role, mocker):
        credentials = {
            'api_key': 'test-key',
            'upload_url': 'https://api.cloudinary.com/v1_1/demo/image/upload',
            'upload_preset': 'user_profile_picture',
            'asset_folder': UploadIntent.USER_PROFILES.value,
            'use_asset_folder_as_public_id_prefix': True,
            'timestamp': 1234567890,
            'image_signatures': [
                {'public_id': 'abc_pfp', 'signature': 'sig123'},
            ],
        }
        mocker.patch(
            'apps.accounts.services.user_service.StorageService.get_upload_credentials',
            return_value=credentials,
        )
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(IMAGE_SIGNATURE_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['api_key'] == 'test-key'
        assert data['public_id'] == 'abc_pfp'
        assert data['signature'] == 'sig123'
        assert data['asset_folder'] == UploadIntent.USER_PROFILES.value

    def test_permission_denied_without_update_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(IMAGE_SIGNATURE_URL)

        assert response.status_code == 403
