from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.serializers.request.report_serializer import GetReportListRequestSerializer
from apps.reports.tests.factories import HazardCategoryFactory, HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestDueAtComputation:
    def test_create_report_sets_due_at_from_category_response_time(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        category = HazardCategoryFactory(response_time_days=10)

        before_create = timezone.now()
        result = ReportService.create_assign_hazard_report(
            reported_by_id=citizen.user_id,
            category_id=category.hazard_id,
            latitude=Decimal("14.599500"),
            longitude=Decimal("120.984200"),
            address="Sampaloc, Manila, Metro Manila",
            description="Deep pothole in the middle of the road",
            is_anonymous=False,
            image_urls=[],
        )
        after_create = timezone.now()

        report = result.value
        assert result.is_success
        assert report.due_at is not None
        assert before_create + timedelta(days=10) <= report.due_at <= after_create + timedelta(days=10)

    def test_due_at_matches_category_response_time(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        category = HazardCategoryFactory(response_time_days=3)

        result = ReportService.create_assign_hazard_report(
            reported_by_id=citizen.user_id,
            category_id=category.hazard_id,
            latitude=Decimal("14.599500"),
            longitude=Decimal("120.984200"),
            address="Sampaloc, Manila, Metro Manila",
            description="Alligator cracks on the road surface",
            is_anonymous=False,
            image_urls=[],
        )

        report = result.value
        # due_at is computed just before the DB insert that stamps created_at,
        # so allow a small tolerance instead of exact equality.
        delta = report.due_at - (report.created_at + timedelta(days=3))
        assert abs(delta.total_seconds()) < 5


@pytest.mark.django_db
class TestIsOverdueProperty:
    def test_open_report_past_due_is_overdue(self):
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            due_at=timezone.now() - timedelta(days=1),
        )
        assert report.is_overdue is True

    def test_open_report_future_due_is_not_overdue(self):
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            due_at=timezone.now() + timedelta(days=2),
        )
        assert report.is_overdue is False

    def test_resolved_report_past_due_is_not_overdue(self):
        report = HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=timezone.now() - timedelta(days=5),
        )
        assert report.is_overdue is False

    def test_closed_report_past_due_is_not_overdue(self):
        report = HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            due_at=timezone.now() - timedelta(days=5),
        )
        assert report.is_overdue is False

    def test_null_due_at_is_never_overdue(self):
        report = HazardReportFactory(status=HazardReports.Status.ASSIGNED, due_at=None)
        assert report.is_overdue is False


@pytest.mark.django_db
class TestOverdueFilter:
    def _supervisor(self, supervisor_role):
        return UserFactory(role=supervisor_role, is_staff=True)

    def test_overdue_filter_returns_only_open_past_due(self, supervisor_role):
        supervisor = self._supervisor(supervisor_role)

        overdue_open = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            due_at=timezone.now() - timedelta(days=1),
        )
        HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            due_at=timezone.now() + timedelta(days=2),
        )
        HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=timezone.now() - timedelta(days=5),
        )

        result = ReportService.list_authorized_reports(
            user=supervisor,
            query_filters={"overdue": True},
        )

        report_numbers = [report.report_number for report in result.value]
        assert report_numbers == [overdue_open.report_number]

    def test_overdue_filter_false_returns_all(self, supervisor_role):
        supervisor = self._supervisor(supervisor_role)

        HazardReportFactory(status=HazardReports.Status.ASSIGNED)
        HazardReportFactory(status=HazardReports.Status.RESOLVED)

        result = ReportService.list_authorized_reports(
            user=supervisor,
            query_filters={"overdue": False},
        )

        assert result.value.count() == 2

    def test_overdue_filter_excludes_null_due_at(self, supervisor_role):
        supervisor = self._supervisor(supervisor_role)

        HazardReportFactory(status=HazardReports.Status.ASSIGNED, due_at=None)

        result = ReportService.list_authorized_reports(
            user=supervisor,
            query_filters={"overdue": True},
        )

        assert result.value.count() == 0


@pytest.mark.django_db
class TestOverdueRequestSerializer:
    def test_staff_overdue_param_is_kept(self, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        serializer = GetReportListRequestSerializer(
            data={"overdue": True},
            context={"user": supervisor},
        )
        serializer.is_valid(raise_exception=True)
        assert serializer.validated_data["overdue"] is True

    def test_non_staff_overdue_param_is_popped(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        serializer = GetReportListRequestSerializer(
            data={"overdue": True},
            context={"user": citizen},
        )
        serializer.is_valid(raise_exception=True)
        assert "overdue" not in serializer.validated_data
