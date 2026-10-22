from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory
from apps.analytics.services import AnalyticService


def _handler(report_officer_role, **kwargs):
    return UserFactory(role=report_officer_role, is_staff=True, **kwargs)


def _viewer(system_admin_role):
    return UserFactory(role=system_admin_role, is_staff=True)


def _resolved_report(handler, *, due_delta, resolved_delta, status=HazardReports.Status.RESOLVED):
    now = timezone.now()
    return HazardReportFactory(
        status=status,
        assigned_to=handler,
        due_at=now + due_delta,
        resolved_at=now + resolved_delta,
    )


def _open_report(handler, *, due_delta, status=HazardReports.Status.DISPATCHED):
    return HazardReportFactory(
        status=status,
        assigned_to=handler,
        due_at=timezone.now() + due_delta,
        resolved_at=None,
    )


def _handler_row(workload, handler):
    return next(
        (row for row in workload["handlers"] if row["user_number"] == handler.user_number),
        None,
    )


def _name(user):
    middle = f" {user.middle_name[0].upper()}." if user.middle_name else ""
    return f"{user.last_name}, {user.first_name}{middle}"


@pytest.mark.django_db
class TestHandlerWorkloadMetrics:
    def test_mixed_outcomes_all_count_as_handled(self, system_admin_role, report_officer_role):
        # Workload, not a score: on-time, late, open-past-due and pending
        # reports all count — nothing is skipped for its outcome.
        viewer = _viewer(system_admin_role)
        handler = _handler(report_officer_role)
        _resolved_report(handler, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))
        _resolved_report(handler, due_delta=timedelta(days=1), resolved_delta=timedelta(days=4))
        _open_report(handler, due_delta=timedelta(days=-1))
        _open_report(handler, due_delta=timedelta(days=3), status=HazardReports.Status.ONGOING)

        workload = AnalyticService.get_handler_workload(user=viewer).value

        row = _handler_row(workload, handler)
        assert row["handled"] == 4
        assert row["resolved"] == 2

    def test_unassigned_report_is_not_counted(self, system_admin_role):
        viewer = _viewer(system_admin_role)
        HazardReportFactory(
            assigned_to=None,
            due_at=timezone.now() + timedelta(days=1),
            resolved_at=None,
        )

        workload = AnalyticService.get_handler_workload(user=viewer).value

        assert workload["handlers"] == []

    def test_null_due_date_is_not_counted(self, system_admin_role, report_officer_role):
        viewer = _viewer(system_admin_role)
        handler = _handler(report_officer_role)
        HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            assigned_to=handler,
            due_at=None,
            resolved_at=timezone.now(),
        )

        workload = AnalyticService.get_handler_workload(user=viewer).value

        assert _handler_row(workload, handler) is None

    def test_rows_created_before_old_cutoff_still_count(self, system_admin_role, report_officer_role, settings):
        # The scoring-era DO47_COMPLIANCE_SINCE exemption is gone: workload
        # counts every assigned report whose deadline falls in the window.
        viewer = _viewer(system_admin_role)
        handler = _handler(report_officer_role)
        report = _resolved_report(handler, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))
        HazardReports.objects.filter(pk=report.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        settings.DO47_COMPLIANCE_SINCE = timezone.now().date() - timedelta(days=1)

        workload = AnalyticService.get_handler_workload(user=viewer).value

        row = _handler_row(workload, handler)
        assert row is not None
        assert row["handled"] == 1

    def test_range_filters_by_due_date(self, system_admin_role, report_officer_role):
        # Due-cohort: only reports whose DEADLINE falls in the range count,
        # regardless of when they were created or resolved.
        viewer = _viewer(system_admin_role)
        handler = _handler(report_officer_role)
        _resolved_report(handler, due_delta=timedelta(days=-30), resolved_delta=timedelta(days=-31))
        fresh = _resolved_report(
            handler, due_delta=timedelta(hours=1), resolved_delta=timedelta(minutes=5)
        )
        fresh_day = timezone.localdate(fresh.due_at).isoformat()

        workload = AnalyticService.get_handler_workload(
            user=viewer, from_date=fresh_day, to_date=fresh_day
        ).value

        row = _handler_row(workload, handler)
        assert row["handled"] == 1
        assert row["resolved"] == 1

    def test_range_excludes_report_due_before_window(self, system_admin_role, report_officer_role):
        viewer = _viewer(system_admin_role)
        handler = _handler(report_officer_role)
        _resolved_report(handler, due_delta=timedelta(days=-5), resolved_delta=timedelta(days=-6))

        today = timezone.localdate().isoformat()
        workload = AnalyticService.get_handler_workload(
            user=viewer, from_date=today, to_date=today
        ).value

        assert _handler_row(workload, handler) is None

    def test_invalid_range_is_rejected(self, system_admin_role):
        viewer = _viewer(system_admin_role)

        result = AnalyticService.get_handler_workload(
            user=viewer, from_date="not-a-date", to_date=None
        )

        assert result.is_success is False
        assert result.error.error_code == "INVALID_ANALYTICS_RANGE"

    def test_handlers_sort_alphabetically_not_by_volume(self, system_admin_role, report_officer_role):
        # The table describes the team — a busy handler is not ranked first.
        viewer = _viewer(system_admin_role)
        busy = _handler(report_officer_role, first_name="Zoe", last_name="Zulu")
        quiet = _handler(report_officer_role, first_name="Ann", last_name="Alpha")
        for _ in range(3):
            _resolved_report(busy, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))
        _resolved_report(quiet, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))

        workload = AnalyticService.get_handler_workload(user=viewer).value

        names = [row["handler_name"] for row in workload["handlers"]]
        assert names.index(_name(quiet)) < names.index(_name(busy))

    def test_scoped_to_viewer_report_read_scope(self, system_admin_role, report_officer_role):
        # Admin (read_all) sees the whole team; an officer (read_assigned)
        # only sees reports sitting on their own desk.
        admin = _viewer(system_admin_role)
        officer = _handler(report_officer_role)
        other = _handler(report_officer_role)
        _resolved_report(officer, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))
        _resolved_report(other, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))

        admin_view = AnalyticService.get_handler_workload(user=admin).value
        officer_view = AnalyticService.get_handler_workload(user=officer).value

        assert _handler_row(admin_view, other) is not None
        assert _handler_row(officer_view, officer) is not None
        assert _handler_row(officer_view, other) is None


@pytest.mark.django_db
class TestHandlerWorkloadEndpoint:
    def test_report_officer_can_read_workload(self, api_client, report_officer_role):
        # Open to every analytics scope now — no supervisor-only gate.
        officer = _handler(report_officer_role)
        _resolved_report(officer, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))

        api_client.force_authenticate(user=officer)
        response = api_client.get("/analytics/handlers/")

        assert response.status_code == 200
        data = response.json()
        row = next(r for r in data["handlers"] if r["user_number"] == officer.user_number)
        assert row["handled"] == 1
        assert row["resolved"] == 1

    def test_officer_only_sees_own_scope(self, api_client, report_officer_role):
        officer = _handler(report_officer_role)
        other = _handler(report_officer_role)
        _resolved_report(officer, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))
        _resolved_report(other, due_delta=timedelta(days=1), resolved_delta=timedelta(hours=1))

        api_client.force_authenticate(user=officer)
        response = api_client.get("/analytics/handlers/")

        assert response.status_code == 200
        numbers = [r["user_number"] for r in response.json()["handlers"]]
        assert officer.user_number in numbers
        assert other.user_number not in numbers

    def test_workload_accepts_a_range(self, api_client, supervisor_role, report_officer_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        handler = _handler(report_officer_role)
        report = _resolved_report(
            handler, due_delta=timedelta(hours=1), resolved_delta=timedelta(minutes=5)
        )
        due_day = timezone.localdate(report.due_at).isoformat()

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(
            "/analytics/handlers/", {"from": due_day, "to": due_day}
        )

        assert response.status_code == 200
        assert any(
            r["user_number"] == handler.user_number
            for r in response.json()["handlers"]
        )

    def test_invalid_range_returns_400(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(
            "/analytics/handlers/", {"from": "01/10/2026", "to": ""}
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_ANALYTICS_RANGE"
