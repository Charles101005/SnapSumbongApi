from decimal import Decimal

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports, ReportImages
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardCategoryFactory, HazardReportFactory


@pytest.mark.django_db
class TestReportDetailView:
    def test_unknown_report_number_returns_400(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/reports/REPT-99999999-N0PE00/")

        assert response.status_code == 400
        assert response.json()["error_code"] == "REPORT_DOES_NOT_EXIST"

    def test_detail_groups_photos_by_phase(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        report = HazardReportFactory(reported_by=UserFactory(), severity="P2")
        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/before.jpg",
            photo_type=ReportImages.PhotoType.BEFORE,
        )
        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/during.jpg",
            photo_type=ReportImages.PhotoType.DURING,
        )
        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/after.jpg",
            photo_type=ReportImages.PhotoType.AFTER,
        )

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.json()["photos"] == {
            "before": ["https://res.cloudinary.com/demo/before.jpg"],
            "during": ["https://res.cloudinary.com/demo/during.jpg"],
            "after": ["https://res.cloudinary.com/demo/after.jpg"],
        }

    def test_citizen_timeline_carries_the_creation_entry(
        self, api_client, citizen_role
    ):
        citizen = UserFactory(role=citizen_role)
        result = ReportService.create_assign_hazard_report(
            reported_by_id=citizen.user_id,
            category_id=HazardCategoryFactory().hazard_id,
            latitude=Decimal("14.599500"),
            longitude=Decimal("120.984200"),
            address="Sampaloc, Manila, Metro Manila",
            description="Collapsed drainage along the main road.",
            is_anonymous=True,
            image_urls=["https://res.cloudinary.com/demo/submit.jpg"],
        )
        report = result.value

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        timeline = response.json()["status_timeline"]
        assert len(timeline) == 1
        entry = timeline[0]
        assert entry["action"] == "CREATE"
        assert entry["from_status"] is None
        assert entry["to_status"] == HazardReports.Status(report.status).label
        assert entry["remarks"] is None
        assert entry["performed_by_role"] is not None
