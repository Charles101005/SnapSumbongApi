from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardCategoryFactory, HazardReportFactory


@pytest.mark.django_db
class TestCategoryChange:
    @staticmethod
    def _officer_and_report(report_officer_role, *, response_time_days=30, **report_kwargs):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        category = HazardCategoryFactory(response_time_days=response_time_days)
        defaults = {
            "assigned_to": officer,
            "category": category,
            "status": HazardReports.Status.UNDER_REVIEW,
            "severity": "P2",
        }
        defaults.update(report_kwargs)
        return officer, HazardReportFactory(**defaults)

    def test_change_under_review_updates_category_sla_and_writes_audit(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        original_category = report.category
        # The defect was noted 10 days ago and sat in review ever since.
        noted_at = timezone.now() - timedelta(days=10)
        HazardReports.objects.filter(pk=report.pk).update(created_at=noted_at)
        report.refresh_from_db()

        corrected = HazardCategoryFactory(response_time_days=3)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "category_id": corrected.hazard_id,
                "remarks": "Citizen picked the wrong category.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.category_id == corrected.hazard_id
        # DO 47 §4.1: SLA stays anchored to creation — with a 3-day window
        # from 10 days ago the report is retroactively overdue.
        assert report.due_at == report.created_at + timedelta(days=3)
        assert report.is_overdue is True

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.CATEGORY_CHANGE)
        assert log.payload["category_change"]["from"] == original_category.hazard_name
        assert log.payload["category_change"]["to"] == corrected.hazard_name
        assert log.payload["remarks"] == "Citizen picked the wrong category."
        assert log.payload["due_at"]["from"] is not None
        assert log.payload["due_at"]["to"] is not None

    def test_change_extends_sla_for_a_longer_category(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(
            report_officer_role, response_time_days=3
        )
        corrected = HazardCategoryFactory(response_time_days=30)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"category_id": corrected.hazard_id, "remarks": "Actually major scaling."},
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.category_id == corrected.hazard_id
        assert report.due_at == report.created_at + timedelta(days=30)
        assert report.is_overdue is False

    @pytest.mark.parametrize(
        "status",
        [
            HazardReports.Status.NEW,
            HazardReports.Status.ASSIGNED,
            HazardReports.Status.ON_HOLD,
            HazardReports.Status.DISPATCHED,
        ],
    )
    def test_change_is_rejected_outside_under_review(
        self, api_client, report_officer_role, status
    ):
        officer, report = self._officer_and_report(report_officer_role, status=status)
        corrected = HazardCategoryFactory(response_time_days=3)
        original_category_id = report.category_id

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"category_id": corrected.hazard_id, "remarks": "Reclassifying."},
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "CATEGORY_CHANGE_NOT_PERMITTED"
        report.refresh_from_db()
        assert report.category_id == original_category_id

    def test_change_without_a_remark_is_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        corrected = HazardCategoryFactory(response_time_days=3)
        original_category_id = report.category_id

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"category_id": corrected.hazard_id},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "MANDATORY_CATEGORY_REMARKS"
        report.refresh_from_db()
        assert report.category_id == original_category_id

    def test_unknown_category_id_is_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        original_category_id = report.category_id

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"category_id": 999999, "remarks": "Reclassifying."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_HAZARD_CATEGORY"
        report.refresh_from_db()
        assert report.category_id == original_category_id

    def test_unchanged_category_is_a_no_op_without_audit_entry(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        due_at_before = report.due_at

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"category_id": report.category_id, "remarks": "No real change."},
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.due_at == due_at_before
        assert not AuditLogs.objects.filter(
            action=AuditLogs.ActionType.CATEGORY_CHANGE
        ).exists()

    def test_category_and_status_can_change_in_one_request(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        corrected = HazardCategoryFactory(response_time_days=3)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "category_id": corrected.hazard_id,
                "status": "DISPATCHED",
                "remarks": "Reclassified to potholes; crew dispatched.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.category_id == corrected.hazard_id
        assert report.status == HazardReports.Status.DISPATCHED
        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.CATEGORY_CHANGE
        ).exists()
        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        ).exists()

    def test_remarks_without_status_or_category_are_still_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"remarks": "No change at all."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_REPORT_UPDATE"


@pytest.mark.django_db
class TestCategoryIdInResponses:
    def test_staff_detail_returns_category_id(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            reported_by=UserFactory(),
            assigned_to=officer,
            status=HazardReports.Status.UNDER_REVIEW,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.json()["category_id"] == report.category_id
        assert response.json()["category"] == report.category.hazard_name

    def test_citizen_detail_hides_category_id(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            reported_by=citizen, status=HazardReports.Status.UNDER_REVIEW
        )

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert "category_id" not in response.json()
        assert "category" not in response.json()

    def test_lookup_categories_carry_response_time_days(
        self, api_client, report_officer_role
    ):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        HazardCategoryFactory(response_time_days=10)

        api_client.force_authenticate(user=officer)
        response = api_client.get("/reports/lookup/")

        assert response.status_code == 200
        categories = response.json()["categories"]
        assert categories
        assert all("response_time_days" in item for item in categories)
        assert categories[0]["response_time_days"] == 10
