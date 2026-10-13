from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports, ReportImages
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory
from apps.analytics.services import AnalyticService


def _add_photo(report, photo_type):
    ReportImages.objects.create(
        report=report,
        image_url="https://res.cloudinary.com/demo/rectification.jpg",
        photo_type=photo_type,
    )


def _resolved_report(
        handler,
        *,
        on_time=True,
        full_photolog=True,
        validator=None,
        due=True,
        status=HazardReports.Status.RESOLVED,
):
    now = timezone.now()
    report = HazardReportFactory(
        status=status,
        assigned_to=handler,
        due_at=(now + timedelta(days=1)) if due else None,
        resolved_at=now if on_time else now + timedelta(days=5),
    )
    if full_photolog:
        _add_photo(report, ReportImages.PhotoType.DURING)
        _add_photo(report, ReportImages.PhotoType.AFTER)
    if validator is not None:
        report.validated_by = validator
        report.save(update_fields=["validated_by"])
    return report


def _handler_row(metrics, handler):
    return next(
        (row for row in metrics["handlers"] if row["user_number"] == handler.user_number),
        None,
    )


def _name(user):
    middle = f" {user.middle_name[0].upper()}." if user.middle_name else ""
    return f"{user.last_name}, {user.first_name}{middle}"


@pytest.mark.django_db
class TestHandlerComplianceMetrics:
    def test_perfect_handler_scores_outstanding(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator=validator)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["sla_on_time_pct"] == 100.0
        assert row["photolog_pct"] == 100.0
        assert row["validation_pct"] == 100.0
        assert row["score"] == 100.0
        assert row["rating"] == "Outstanding"
        assert metrics["weights"]["sla_on_time"] == 60.0

    def test_non_compliant_handler_scores_poor(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, on_time=False, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["sla_on_time_pct"] == 0.0
        assert row["photolog_pct"] == 0.0
        assert row["validation_pct"] == 0.0
        assert row["score"] == 0.0
        assert row["rating"] == "Poor"

    def test_weights_combine_component_percentages(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator=validator)
        _resolved_report(handler, on_time=False, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 2
        assert row["sla_on_time_pct"] == 50.0
        assert row["photolog_pct"] == 50.0
        assert row["validation_pct"] == 50.0
        assert row["score"] == 50.0
        assert row["rating"] == "Poor"

    def test_missing_due_dates_renormalize_remaining_weights(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator=validator, due=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["sla_on_time_pct"] is None
        # 25-weight photolog + 15-weight validation, both at 100% -> 100.
        assert row["score"] == 100.0
        assert row["rating"] == "Outstanding"

    def test_self_validation_counts_as_non_compliant(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator=handler)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["validation_pct"] == 0.0

    def test_unresolved_reports_are_excluded(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            assigned_to=handler,
            due_at=timezone.now() + timedelta(days=2),
        )

        metrics = AnalyticService.get_handler_compliance_metrics().value

        assert _handler_row(metrics, handler) is None

    def test_handlers_ranked_by_score(self, report_officer_role):
        strong = UserFactory(role=report_officer_role, is_staff=True)
        weak = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(strong, validator=validator)
        _resolved_report(weak, on_time=False, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        names = [row["handler_name"] for row in metrics["handlers"]]
        assert names.index(_name(strong)) < names.index(_name(weak))


@pytest.mark.django_db
class TestComplianceEndpoint:
    def test_supervisor_can_read_compliance(self, api_client, supervisor_role, report_officer_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        handler = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator=validator)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/analytics/compliance/")

        assert response.status_code == 200
        data = response.json()
        assert data["weights"]["sla_on_time"] == 60.0
        assert any(row["user_number"] == handler.user_number for row in data["handlers"])

    def test_report_officer_cannot_read_compliance(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=officer)
        response = api_client.get("/analytics/compliance/")

        assert response.status_code == 403
