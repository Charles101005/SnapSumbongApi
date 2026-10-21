import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.analytics.services import AnalyticService


def _seed_reports(citizen_role, report_officer_role):
    """Four reports across three reporters and two handlers.

    owner:      2 NEW reports assigned to `handler`
    handler:    those 2 plus 1 RESOLVED report from someone else
    other:      1 CLOSED report assigned to `second_handler`
    """
    owner = UserFactory(role=citizen_role)
    handler = UserFactory(role=report_officer_role, is_staff=True)
    second_handler = UserFactory(role=report_officer_role, is_staff=True)
    other_reporter = UserFactory(role=citizen_role)

    HazardReportFactory(
        reported_by=owner, assigned_to=handler, status=HazardReports.Status.NEW
    )
    HazardReportFactory(
        reported_by=owner, assigned_to=handler, status=HazardReports.Status.NEW
    )
    HazardReportFactory(
        reported_by=other_reporter,
        assigned_to=handler,
        status=HazardReports.Status.RESOLVED,
    )
    HazardReportFactory(
        reported_by=other_reporter,
        assigned_to=second_handler,
        status=HazardReports.Status.CLOSED,
    )
    return owner, handler


@pytest.mark.django_db
class TestGetAuthorizedReportMetrics:
    def test_read_all_metrics_sees_every_report(
        self, supervisor_role, citizen_role, report_officer_role
    ):
        _seed_reports(citizen_role, report_officer_role)

        metrics = AnalyticService.get_authorized_report_metrics(
            UserFactory(role=supervisor_role)
        ).value

        assert metrics["total_count"] == 4
        assert metrics["count_by_status"] == {
            "new": 2,
            "resolved": 1,
            "closed": 1,
        }

    def test_read_assigned_metrics_sees_only_assigned_reports(
        self, supervisor_role, citizen_role, report_officer_role
    ):
        _, handler = _seed_reports(citizen_role, report_officer_role)

        metrics = AnalyticService.get_authorized_report_metrics(handler).value

        assert metrics["total_count"] == 3
        assert metrics["count_by_status"] == {"new": 2, "resolved": 1}

    def test_read_own_metrics_sees_only_submitted_reports(
        self, supervisor_role, citizen_role, report_officer_role
    ):
        owner, _ = _seed_reports(citizen_role, report_officer_role)

        metrics = AnalyticService.get_authorized_report_metrics(owner).value

        assert metrics["total_count"] == 2
        assert metrics["count_by_status"] == {"new": 2}

    def test_user_without_reports_gets_empty_counts(self, citizen_role):
        user = UserFactory(role=citizen_role)

        metrics = AnalyticService.get_authorized_report_metrics(user).value

        assert metrics["total_count"] == 0
        assert metrics["count_by_status"] == {}


@pytest.mark.django_db
class TestGetUserActivityMetrics:
    def test_unknown_user_number_is_an_error(self):
        result = AnalyticService.get_user_activity_metrics(
            user_number="NO-SUCH-USER",
            is_staff=False,
        )

        assert not result.is_success
        assert result.error.error_code == "USER_NOT_FOUND"

    def test_staff_number_on_the_citizen_endpoint_is_an_error(
        self, report_officer_role
    ):
        staff = UserFactory(role=report_officer_role, is_staff=True)

        result = AnalyticService.get_user_activity_metrics(
            user_number=staff.user_number,
            is_staff=False,
        )

        assert not result.is_success
        assert result.error.error_code == "USER_NOT_FOUND"

    def test_staff_role_without_assignment_permission_is_rejected(
        self, citizen_role
    ):
        staff = UserFactory(role=citizen_role, is_staff=True)

        result = AnalyticService.get_user_activity_metrics(
            user_number=staff.user_number,
            is_staff=True,
        )

        assert not result.is_success
        assert result.error.error_code == "METRICS_NOT_APPLICABLE_TO_ROLE"

    def test_staff_activity_counts_assigned_reports(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        bystander = UserFactory()
        HazardReportFactory(
            assigned_to=handler, status=HazardReports.Status.RESOLVED
        )
        HazardReportFactory(
            assigned_to=handler, status=HazardReports.Status.RESOLVED
        )
        HazardReportFactory(assigned_to=handler, status=HazardReports.Status.NEW)
        # Reported by the handler but assigned to someone else: not "handled".
        HazardReportFactory(
            assigned_to=bystander, reported_by=handler, status=HazardReports.Status.NEW
        )

        result = AnalyticService.get_user_activity_metrics(
            user_number=handler.user_number,
            is_staff=True,
        )

        assert result.is_success
        assert result.value == {
            "total_reports_handled": 3,
            "total_reports_resolved": 2,
        }

    def test_staff_with_no_resolved_reports_reports_zero(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(assigned_to=handler, status=HazardReports.Status.NEW)

        result = AnalyticService.get_user_activity_metrics(
            user_number=handler.user_number,
            is_staff=True,
        )

        assert result.is_success
        assert result.value == {
            "total_reports_handled": 1,
            "total_reports_resolved": 0,
        }

    def test_citizen_activity_counts_submitted_reports(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        handler = UserFactory(is_staff=True)
        HazardReportFactory(
            reported_by=citizen, assigned_to=handler, status=HazardReports.Status.NEW
        )
        HazardReportFactory(
            reported_by=citizen,
            assigned_to=handler,
            status=HazardReports.Status.RESOLVED,
        )
        # Assigned to the citizen but submitted by someone else: not "submitted".
        HazardReportFactory(
            reported_by=UserFactory(role=citizen_role),
            assigned_to=citizen,
            status=HazardReports.Status.NEW,
        )

        result = AnalyticService.get_user_activity_metrics(
            user_number=citizen.user_number,
            is_staff=False,
        )

        assert result.is_success
        assert result.value == {
            "total_reports_submitted": 2,
            "total_reports_resolved": 1,
        }

    def test_citizen_without_reports_gets_zeroes(self, citizen_role):
        citizen = UserFactory(role=citizen_role)

        result = AnalyticService.get_user_activity_metrics(
            user_number=citizen.user_number,
            is_staff=False,
        )

        assert result.is_success
        assert result.value == {
            "total_reports_submitted": 0,
            "total_reports_resolved": 0,
        }
