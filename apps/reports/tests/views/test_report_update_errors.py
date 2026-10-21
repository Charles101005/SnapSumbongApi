import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports, ReportImages
from apps.reports.tests.factories import HazardReportFactory
from external.storage import StorageService


@pytest.mark.django_db
class TestReportPatchErrors:
    @staticmethod
    def _officer_and_report(report_officer_role, **report_kwargs):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        defaults = {
            "assigned_to": officer,
            "status": HazardReports.Status.UNDER_REVIEW,
            "severity": "P2",
        }
        defaults.update(report_kwargs)
        report = HazardReportFactory(**defaults)
        return officer, report

    def test_unknown_report_returns_400(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            "/reports/REPT-99999999-N0PE00/",
            {"remarks": "Ping."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "REPORT_DOES_NOT_EXIST"

    def test_remarks_without_a_status_are_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"remarks": "No status change."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_REPORT_UPDATE"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW

    def test_nonexistent_status_string_is_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "TOTALLY_BOGUS"},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_REPORT_STATUS"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW

    def test_transition_to_the_current_status_is_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "UNDER_REVIEW"},
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "DUPLICATE_STATUS_TRANSITION"

    def test_empty_patch_is_a_no_op(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/", {}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "Operation completed successfully."
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity == "P2"


@pytest.mark.django_db
class TestResolveWithPhotolog:
    @staticmethod
    def _resolution_url(file_name):
        base = StorageService.get_expected_response_base_url()
        return f"{base}report_resolutions/2026/10/{file_name}.jpg"

    @staticmethod
    def _officer_and_report(report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            assigned_to=officer,
            status=HazardReports.Status.UNDER_REVIEW,
            severity="P2",
        )
        return officer, report

    def test_valid_photolog_resolves_the_report(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        payload = {
            "status": "RESOLVED",
            "remarks": "Pothole patched and sealed.",
            "validated_by_name": "Engr. Dela Cruz",
            "resolution_images": [
                {
                    "image_url": self._resolution_url("img_during"),
                    "photo_type": "DURING",
                },
                {
                    "image_url": self._resolution_url("img_after"),
                    "photo_type": "AFTER",
                },
            ],
        }

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/", payload, format="json"
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.resolved_at is not None
        assert report.validated_by_name == "Engr. Dela Cruz"
        photo_types = set(report.images.values_list("photo_type", flat=True))
        assert photo_types == {
            ReportImages.PhotoType.DURING,
            ReportImages.PhotoType.AFTER,
        }

    def test_foreign_image_url_is_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        payload = {
            "status": "RESOLVED",
            "validated_by_name": "Engr. Dela Cruz",
            "resolution_images": [
                {
                    "image_url": "https://evil.example.com/photo.jpg",
                    "photo_type": "DURING",
                },
            ],
        }

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/", payload, format="json"
        )

        assert response.status_code == 400
        assert "Invalid URL" in response.content.decode()
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
