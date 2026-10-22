from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory
from apps.analytics.services import AnalyticService


def _handler(report_officer_role):
    return UserFactory(role=report_officer_role, is_staff=True)


def _range_for(*reports, pad_days=0):
    """Inclusive ISO range covering every report's due/created/resolved day."""
    dates = []
    for report in reports:
        for value in (report.created_at, report.resolved_at, report.due_at):
            if value is not None:
                dates.append(timezone.localdate(value))
    if not dates:
        today = timezone.localdate()
        return {"from_date": today.isoformat(), "to_date": today.isoformat()}
    return {
        "from_date": (min(dates) - timedelta(days=pad_days)).isoformat(),
        "to_date": (max(dates) + timedelta(days=pad_days)).isoformat(),
    }


def _today_range():
    today = timezone.localdate().isoformat()
    return {"from_date": today, "to_date": today}


def _backdate(report, *, created=None, resolved=None, due=None):
    updates = {}
    if created is not None:
        updates["created_at"] = created
    if resolved is not None:
        updates["resolved_at"] = resolved
    if due is not None:
        updates["due_at"] = due
    HazardReports.objects.filter(pk=report.pk).update(**updates)
    report.refresh_from_db()
    return report


@pytest.mark.django_db
class TestOverviewIntake:
    def test_counts_reports_filed_in_range(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(severity="P1")
        HazardReportFactory(severity="P3")

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["intake"]["total"] == 2
        assert result["intake"]["by_severity"]["P1"] == 1
        assert result["intake"]["by_severity"]["P3"] == 1
        assert result["intake"]["by_severity"]["unknown"] == 0

    def test_reports_outside_range_are_excluded(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        old = HazardReportFactory(severity="P2")
        _backdate(old, created=timezone.now() - timedelta(days=10))
        HazardReportFactory(severity="P1")

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["intake"]["total"] == 1
        assert result["intake"]["by_severity"]["P2"] == 0

    def test_daily_series_and_status_mix(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(severity="P1")
        HazardReportFactory(severity="P2")
        today = timezone.localdate().isoformat()

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["intake"]["daily"] == [{"date": today, "count": 2}]
        assert result["intake"]["by_status"]["new"] == 2
        assert result["intake"]["by_status"]["resolved"] == 0
        assert result["range"] == {"from": today, "to": today}

    def test_unbounded_range_returns_data_span(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        old = HazardReportFactory()
        span_from = timezone.localdate() - timedelta(days=10)
        HazardReports.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
        HazardReportFactory()

        result = AnalyticService.get_report_overview(user=supervisor).value

        assert result["span"]["from"] == span_from.isoformat()
        assert result["span"]["to"] == timezone.localdate().isoformat()
        assert result["intake"]["total"] == 2

    def test_all_severity_levels_default_to_zero(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(severity="P1")

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        for level in ("P2", "P3", "P4", "P5"):
            assert result["intake"]["by_severity"][level] == 0


@pytest.mark.django_db
class TestOverviewDelivery:
    def test_avg_daily_weekly_and_slowest_resolutions(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        now = timezone.now()
        fast = HazardReportFactory(status=HazardReports.Status.RESOLVED, resolved_at=now)
        _backdate(fast, created=now - timedelta(days=1))
        slow = HazardReportFactory(status=HazardReports.Status.RESOLVED, resolved_at=now)
        _backdate(slow, created=now - timedelta(days=5))

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        delivery = result["delivery"]
        assert delivery["resolved"] == 2
        assert delivery["avg_days"] == 3.0
        assert len(delivery["daily"]) == 1
        assert delivery["daily"][0]["date"] == timezone.localdate(now).isoformat()
        assert delivery["daily"][0]["resolved"] == 2
        assert delivery["daily"][0]["avg_days"] == 3.0
        assert len(delivery["weekly"]) == 1
        assert delivery["weekly"][0]["resolved"] == 2
        assert delivery["weekly"][0]["avg_days"] == 3.0
        assert delivery["slowest"][0]["report_number"] == slow.report_number
        assert delivery["slowest"][0]["days"] == 5.0
        assert len(delivery["slowest"]) == 2

    def test_no_resolutions_yields_null_avg(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(status=HazardReports.Status.NEW)

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["delivery"]["resolved"] == 0
        assert result["delivery"]["avg_days"] is None
        assert result["delivery"]["daily"] == []
        assert result["delivery"]["weekly"] == []
        assert result["delivery"]["slowest"] == []

    def test_resolutions_outside_range_are_excluded(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        old = HazardReportFactory(status=HazardReports.Status.RESOLVED, resolved_at=timezone.now())
        _backdate(old, created=timezone.now() - timedelta(days=10), resolved=timezone.now() - timedelta(days=10))
        HazardReportFactory(status=HazardReports.Status.NEW)

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["delivery"]["resolved"] == 0


@pytest.mark.django_db
class TestOverviewSlaOutcomes:
    def test_classifies_on_time_late_breach_and_pending(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        now = timezone.now()
        # On time: resolved now, due later today.
        HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=now + timedelta(hours=6),
            resolved_at=now,
        )
        # Late: due today, resolved two days after the deadline.
        HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=now,
            resolved_at=now + timedelta(days=2),
        )
        # Breach: still open past a deadline that already passed.
        HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            due_at=now - timedelta(days=1),
        )
        # Pending: open, deadline still ahead.
        HazardReportFactory(
            status=HazardReports.Status.ONGOING,
            due_at=now + timedelta(days=3),
        )

        result = AnalyticService.get_report_overview(
            user=supervisor,
            from_date=(timezone.localdate() - timedelta(days=1)).isoformat(),
            to_date=(timezone.localdate() + timedelta(days=3)).isoformat(),
        ).value

        sla = result["sla"]
        assert sla["on_time"] == 1
        assert sla["late"] == 1
        assert sla["breach"] == 1
        assert sla["pending"] == 1
        assert sla["judged"] == 3
        assert sla["on_time_pct"] == 33.3

    def test_never_resolved_terminal_rows_are_not_judged(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            due_at=timezone.now() - timedelta(days=2),
            resolved_at=None,
        )

        result = AnalyticService.get_report_overview(user=supervisor).value

        assert result["sla"]["judged"] == 0
        assert result["sla"]["on_time_pct"] is None

    def test_null_due_date_rows_are_not_judged(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=None,
            resolved_at=timezone.now(),
        )

        result = AnalyticService.get_report_overview(user=supervisor).value

        assert result["sla"]["judged"] == 0

    def test_pre_enforcement_rows_are_not_judged(self, supervisor_role, settings):
        supervisor = _handler(supervisor_role)
        report = HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=timezone.now() + timedelta(days=1),
            resolved_at=timezone.now(),
        )
        _backdate(report, created=timezone.now() - timedelta(days=10))
        settings.DO47_COMPLIANCE_SINCE = timezone.now().date() - timedelta(days=1)

        result = AnalyticService.get_report_overview(user=supervisor).value

        assert result["sla"]["judged"] == 0

    def test_due_cohort_excludes_out_of_range_deadlines(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        # Resolved on time with a deadline ten days ago.
        old = HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            due_at=timezone.now() - timedelta(days=10),
            resolved_at=timezone.now() - timedelta(days=11),
        )
        _backdate(old, created=timezone.now() - timedelta(days=12))

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["sla"]["judged"] == 0


@pytest.mark.django_db
class TestOverviewLiveBacklog:
    def test_live_counts_ignore_the_selected_range(self, supervisor_role):
        supervisor = _handler(supervisor_role)
        overdue = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            due_at=timezone.now() - timedelta(days=5),
        )
        _backdate(overdue, created=timezone.now() - timedelta(days=10))
        HazardReportFactory(
            status=HazardReports.Status.ONGOING,
            due_at=timezone.now() + timedelta(days=2),
        )
        HazardReportFactory(status=HazardReports.Status.RESOLVED, resolved_at=timezone.now())

        result = AnalyticService.get_report_overview(
            user=supervisor, **_today_range()
        ).value

        assert result["live"]["open"] == 2
        assert result["live"]["overdue"] == 1


@pytest.mark.django_db
class TestOverviewScoping:
    def test_officer_sees_only_assigned_reports(self, report_officer_role, supervisor_role):
        officer = _handler(report_officer_role)
        other = _handler(supervisor_role)
        HazardReportFactory(assigned_to=officer, severity="P1")
        HazardReportFactory(assigned_to=other, severity="P2")

        result = AnalyticService.get_report_overview(user=officer, **_today_range()).value

        assert result["intake"]["total"] == 1
        assert result["intake"]["by_severity"]["P1"] == 1
        assert result["intake"]["by_severity"]["P2"] == 0

    def test_citizen_sees_only_own_filings(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        HazardReportFactory(reported_by=citizen, severity="P4")
        HazardReportFactory(severity="P1")

        result = AnalyticService.get_report_overview(user=citizen, **_today_range()).value

        assert result["intake"]["total"] == 1
        assert result["intake"]["by_severity"]["P4"] == 1


@pytest.mark.django_db
class TestOverviewRangeValidation:
    def test_invalid_date_is_rejected(self, supervisor_role):
        supervisor = _handler(supervisor_role)

        result = AnalyticService.get_report_overview(
            user=supervisor, from_date="not-a-date", to_date=None
        )

        assert result.is_success is False
        assert result.error.error_code == "INVALID_ANALYTICS_RANGE"

    def test_backwards_range_is_rejected(self, supervisor_role):
        supervisor = _handler(supervisor_role)

        result = AnalyticService.get_report_overview(
            user=supervisor, from_date="2026-10-31", to_date="2026-10-01"
        )

        assert result.is_success is False


@pytest.mark.django_db
class TestOverviewEndpoint:
    def test_officer_can_read_overview(self, api_client, report_officer_role):
        officer = _handler(report_officer_role)
        HazardReportFactory(assigned_to=officer, severity="P1")

        api_client.force_authenticate(user=officer)
        today = timezone.localdate().isoformat()
        response = api_client.get(
            "/analytics/overview/", {"from": today, "to": today}
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"range", "span", "intake", "delivery", "sla", "live"}
        assert data["intake"]["total"] == 1

    def test_citizen_can_read_own_overview(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/analytics/overview/")

        assert response.status_code == 200

    def test_invalid_range_returns_400(self, api_client, supervisor_role):
        supervisor = _handler(supervisor_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(
            "/analytics/overview/", {"from": "31-10-2026", "to": ""}
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_ANALYTICS_RANGE"
