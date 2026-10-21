import pytest

from apps.audits.models import AuditLogs
from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports, ReportImages
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardCategoryFactory
from external.storage import StorageService


def _valid_payload(category, **overrides):
    base = {
        "category_id": category.hazard_id,
        "latitude": "14.599500",
        "longitude": "120.984200",
        "address": "Sampaloc, Manila, Metro Manila",
        "description": "Deep pothole blocking the bike lane.",
        "is_anonymous": False,
        "image_urls": [
            f"{StorageService.get_expected_response_base_url()}"
            f"hazard_reports/2026/10/batch_img1.jpg"
        ],
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
class TestCreateReportView:
    def test_citizen_can_create_a_report(self, api_client, citizen_role):
        category = HazardCategoryFactory()
        user = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/reports/", _valid_payload(category), format="json"
        )

        assert response.status_code == 201
        data = response.json()
        assert data["report_number"].startswith("REPT-")

        report = HazardReports.objects.get(report_number=data["report_number"])
        assert report.reported_by_id == user.user_id
        assert report.category_id == category.hazard_id
        assert list(
            report.images.values_list("photo_type", flat=True)
        ) == [ReportImages.PhotoType.BEFORE]

    def test_foreign_image_url_is_rejected(self, api_client, citizen_role):
        category = HazardCategoryFactory()
        user = UserFactory(role=citizen_role)
        payload = _valid_payload(
            category,
            image_urls=["https://evil.example.com/not-ours.jpg"],
        )

        api_client.force_authenticate(user=user)
        response = api_client.post("/reports/", payload, format="json")

        assert response.status_code == 400

    def test_unknown_category_is_rejected(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        payload = _valid_payload(HazardCategoryFactory(), category_id=999999)

        api_client.force_authenticate(user=user)
        response = api_client.post("/reports/", payload, format="json")

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_HAZARD_CATEGORY"

    def test_role_without_create_permission_is_denied(
        self, api_client, supervisor_role
    ):
        category = HazardCategoryFactory()
        user = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/reports/", _valid_payload(category), format="json"
        )

        assert response.status_code == 403
        assert not HazardReports.objects.exists()

    def test_creation_logs_a_create_audit_entry(self, api_client, citizen_role):
        category = HazardCategoryFactory()
        user = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/reports/", _valid_payload(category), format="json"
        )

        assert response.status_code == 201
        report = ReportService.get_authorized_reports(
            user=user,
            report_number=response.json()["report_number"],
        ).value
        actions = [log.action for log in report.audit_logs.all()]
        assert AuditLogs.ActionType.CREATE in actions
        create_log = report.audit_logs.get(action=AuditLogs.ActionType.CREATE)
        assert (
            create_log.payload["initial_status"]
            == HazardReports.Status(report.status).label
        )
