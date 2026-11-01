import pytest
from django.conf import settings

from apps.accounts.models import CitizenWarnings
from apps.accounts.tests.factories import UserFactory
from external.storage import UploadIntent


CREDENTIALS = {
    "upload_url": "https://api.cloudinary.com/v1_1/demo/image/upload",
    "api_key": "test-api-key",
    "upload_preset": "hazard_report_image",
    "image_signatures": [{"public_id": "batch_img1", "signature": "sig"}],
    "asset_folder": "hazard_reports/2026/10",
    "use_asset_folder_as_public_id_prefix": True,
    "timestamp": 1760000000,
}


@pytest.mark.django_db
class TestReportImageSignatureView:
    def test_citizen_uploads_use_the_hazard_reports_intent(
        self, api_client, citizen_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        user = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/reports/image-signature/", {"image_count": 2})

        assert response.status_code == 200
        assert response.json()["api_key"] == "test-api-key"
        kwargs = storage_mock.call_args.kwargs
        assert kwargs["intent"] == UploadIntent.HAZARD_REPORTS
        assert kwargs["folder_path"].startswith(UploadIntent.HAZARD_REPORTS.value)
        assert len(kwargs["file_names"]) == 2
        assert kwargs["file_names"][0].endswith("_img1")
        assert kwargs["file_names"][1].endswith("_img2")

    def test_officer_uploads_use_the_resolution_intent(
        self, api_client, report_officer_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=officer)
        response = api_client.get("/reports/image-signature/", {"image_count": 1})

        assert response.status_code == 200
        kwargs = storage_mock.call_args.kwargs
        assert kwargs["intent"] == UploadIntent.REPORT_RESOLUTION
        assert kwargs["folder_path"].startswith(UploadIntent.REPORT_RESOLUTION.value)

    def test_zero_image_count_is_rejected(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/reports/image-signature/", {"image_count": 0})

        assert response.status_code == 400

    def test_image_count_above_the_max_is_rejected(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=user)
        response = api_client.get(
            "/reports/image-signature/",
            {"image_count": settings.STORAGE_CONFIG["MAX_SIGNATURE_COUNT"] + 1},
        )

        assert response.status_code == 400

    def test_role_without_upload_permission_is_denied(
        self, api_client, supervisor_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        user = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=user)
        response = api_client.get("/reports/image-signature/", {"image_count": 1})

        assert response.status_code == 403
        storage_mock.assert_not_called()

    def test_citizen_with_three_warnings_cannot_request_a_signature(
        self, api_client, citizen_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        user = UserFactory(role=citizen_role)
        for _ in range(3):
            CitizenWarnings.objects.create(user=user, reason="Repeated invalid reports.")

        api_client.force_authenticate(user=user)
        response = api_client.get("/reports/image-signature/", {"image_count": 1})

        assert response.status_code == 403
        assert response.json()["error_code"] == "REPORT_BLOCKED_BY_WARNINGS"
        storage_mock.assert_not_called()

    def test_citizen_below_the_warning_limit_can_request_a_signature(
        self, api_client, citizen_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        user = UserFactory(role=citizen_role)
        for _ in range(2):
            CitizenWarnings.objects.create(user=user, reason="Repeated invalid reports.")

        api_client.force_authenticate(user=user)
        response = api_client.get("/reports/image-signature/", {"image_count": 1})

        assert response.status_code == 200
        storage_mock.assert_called_once()

    def test_officer_with_three_warnings_can_still_request_resolution_signatures(
        self, api_client, report_officer_role, mocker
    ):
        storage_mock = mocker.patch(
            "external.storage.StorageService.get_upload_credentials",
            return_value=CREDENTIALS,
        )
        officer = UserFactory(role=report_officer_role, is_staff=True)
        for _ in range(3):
            CitizenWarnings.objects.create(user=officer, reason="Legacy warning.")

        api_client.force_authenticate(user=officer)
        response = api_client.get("/reports/image-signature/", {"image_count": 1})

        assert response.status_code == 200
        assert storage_mock.call_args.kwargs["intent"] == UploadIntent.REPORT_RESOLUTION
