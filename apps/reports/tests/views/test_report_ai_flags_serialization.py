import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import ReportImages
from apps.reports.tests.factories import HazardReportFactory


FLAGGED_IMAGE = "https://res.cloudinary.com/demo/flagged.jpg"


@pytest.mark.django_db
class TestReportAiFlagSerialization:
    def test_staff_list_and_detail_expose_ai_flags(
            self, api_client, supervisor_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        report = HazardReportFactory(
            reported_by=UserFactory(),
            severity="P2",
            is_ai_flagged=True,
            ai_flag_reasons=["AI_GENERATED"],
        )
        ReportImages.objects.create(
            report=report,
            image_url=FLAGGED_IMAGE,
            photo_type=ReportImages.PhotoType.BEFORE,
            is_ai_flagged=True,
        )

        api_client.force_authenticate(user=supervisor)

        list_response = api_client.get("/reports/")
        assert list_response.status_code == 200
        row = list_response.json()["results"][0]
        assert row["is_ai_flagged"] is True
        assert row["ai_flag_reasons"] == ["AI_GENERATED"]
        assert "ai_flag_review_status" not in row

        detail_response = api_client.get(f"/reports/{report.report_number}/")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["is_ai_flagged"] is True
        assert detail["ai_flag_reasons"] == ["AI_GENERATED"]
        assert "ai_flag_review_status" not in detail
        assert "ai_flag_reviewed_by" not in detail
        assert "ai_flag_reviewed_at" not in detail
        assert detail["image_ai_flags"] == [{
            "image_url": FLAGGED_IMAGE,
            "is_ai_flagged": True,
        }]

    def test_citizen_responses_hide_ai_flags(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            reported_by=citizen,
            is_ai_flagged=True,
            ai_flag_reasons=["AI_GENERATED"],
        )
        ReportImages.objects.create(
            report=report,
            image_url=FLAGGED_IMAGE,
            photo_type=ReportImages.PhotoType.BEFORE,
            is_ai_flagged=True,
        )

        api_client.force_authenticate(user=citizen)

        list_response = api_client.get("/reports/")
        assert list_response.status_code == 200
        row = list_response.json()["results"][0]
        assert "is_ai_flagged" not in row
        assert "ai_flag_reasons" not in row

        detail_response = api_client.get(f"/reports/{report.report_number}/")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert "is_ai_flagged" not in detail
        assert "ai_flag_reasons" not in detail
        assert "image_ai_flags" not in detail
