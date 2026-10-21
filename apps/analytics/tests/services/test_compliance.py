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
        validator_name=None,
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
    if validator_name is not None:
        report.validated_by_name = validator_name
        report.validated_by = handler
        report.save(update_fields=["validated_by_name", "validated_by"])
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
        _resolved_report(handler, validator_name="Engr. Dela Cruz")

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
        _resolved_report(handler, validator_name="Engr. Dela Cruz")
        _resolved_report(handler, on_time=False, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 2
        assert row["sla_on_time_pct"] == 50.0
        assert row["photolog_pct"] == 50.0
        assert row["validation_pct"] == 50.0
        assert row["score"] == 50.0
        assert row["rating"] == "Poor"

    def test_null_due_date_rows_are_counted_but_not_scored(self, report_officer_role):
        # A null due_at marks a pre-enforcement row (predates SLA tracking and
        # the DURING/AFTER photolog schema): activity counts, scoring does not.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator_name="Engr. Dela Cruz", due=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["sla_on_time_pct"] is None
        assert row["photolog_pct"] is None
        assert row["validation_pct"] is None
        assert row["score"] is None
        assert row["rating"] == "No Data"

    def test_validator_matching_handler_name_counts_as_non_compliant(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator_name=_name(handler))

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["validation_pct"] == 0.0

    def test_missing_validator_name_counts_as_non_compliant(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler)

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

    def test_on_hold_reports_never_reach_scoring(self, report_officer_role):
        # On-Hold (transferred to another department) is phase 2: not a
        # resolved/closed row, so it contributes nothing to the scorecard.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(
            status=HazardReports.Status.ON_HOLD,
            assigned_to=handler,
            due_at=timezone.now() + timedelta(days=2),
        )

        metrics = AnalyticService.get_handler_compliance_metrics().value

        assert _handler_row(metrics, handler) is None

    def test_force_closed_transfer_counts_but_exempts_components(self, report_officer_role):
        # ON_HOLD -> CLOSED transfer: never resolved, so the photolog,
        # validation and SLA obligations never applied to it.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            assigned_to=handler,
            due_at=timezone.now() + timedelta(days=2),
        )

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["sla_on_time_pct"] is None
        assert row["photolog_pct"] is None
        assert row["validation_pct"] is None
        assert row["score"] is None
        assert row["rating"] == "No Data"

    def test_force_close_does_not_drag_down_scored_work(self, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator_name="Engr. Dela Cruz")
        HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            assigned_to=handler,
            due_at=timezone.now() + timedelta(days=2),
        )

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 2
        assert row["sla_on_time_pct"] == 100.0
        assert row["photolog_pct"] == 100.0
        assert row["validation_pct"] == 100.0
        assert row["score"] == 100.0

    def test_force_close_from_resolved_is_still_scored(self, report_officer_role):
        # The report did go through RESOLVED (resolved_at stamped), so a
        # later staff force-close keeps it under scoring.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(
            handler,
            validator_name="Engr. Dela Cruz",
            status=HazardReports.Status.CLOSED,
        )

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["score"] == 100.0

    def test_legacy_photolog_row_does_not_floor_perfect_handler(self, report_officer_role):
        # Pre-enforcement row: null due_at, old resolution photos backfilled
        # as AFTER only (migration 0014), no validator name recorded.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        legacy = _resolved_report(handler, full_photolog=False, due=False)
        _add_photo(legacy, ReportImages.PhotoType.AFTER)
        _resolved_report(handler, validator_name="Engr. Dela Cruz")

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 2
        assert row["sla_on_time_pct"] == 100.0
        assert row["photolog_pct"] == 100.0
        assert row["validation_pct"] == 100.0
        assert row["score"] == 100.0

    def test_rows_created_before_compliance_cutoff_are_exempt(self, report_officer_role, settings):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        report = _resolved_report(handler, full_photolog=False)
        HazardReports.objects.filter(pk=report.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        settings.DO47_COMPLIANCE_SINCE = timezone.now().date() - timedelta(days=1)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["sla_on_time_pct"] is None
        assert row["photolog_pct"] is None
        assert row["validation_pct"] is None
        assert row["score"] is None
        assert row["rating"] == "No Data"

    def test_handlers_ranked_by_score(self, report_officer_role):
        strong = UserFactory(role=report_officer_role, is_staff=True)
        weak = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(strong, validator_name="Engr. Dela Cruz")
        _resolved_report(weak, on_time=False, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        names = [row["handler_name"] for row in metrics["handlers"]]
        assert names.index(_name(strong)) < names.index(_name(weak))

    def test_photolog_half_miss_scores_seventies_satisfactory(self, report_officer_role):
        # SLA 100 (60) + photolog 50 (25) + validation 0 (15) = 72.5.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, full_photolog=True)
        _resolved_report(handler, full_photolog=False)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["sla_on_time_pct"] == 100.0
        assert row["photolog_pct"] == 50.0
        assert row["validation_pct"] == 0.0
        assert row["score"] == 72.5
        assert row["rating"] == "Satisfactory"

    def test_confirmed_but_unresolved_row_scores_photolog_without_sla(
        self, report_officer_role
    ):
        # A row confirmed without a resolve timestamp cannot be judged for
        # SLA (no resolved_at to compare against due_at), but its photolog
        # and validation obligations still apply: photolog 100 (25) +
        # validation 0 (15) renormalizes to 62.5.
        handler = UserFactory(role=report_officer_role, is_staff=True)
        now = timezone.now()
        report = HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            assigned_to=handler,
            due_at=now + timedelta(days=1),
            resolved_at=None,
            confirmed_at=now,
        )
        _add_photo(report, ReportImages.PhotoType.DURING)
        _add_photo(report, ReportImages.PhotoType.AFTER)

        metrics = AnalyticService.get_handler_compliance_metrics().value

        row = _handler_row(metrics, handler)
        assert row["resolved_count"] == 1
        assert row["sla_on_time_pct"] is None
        assert row["photolog_pct"] == 100.0
        assert row["validation_pct"] == 0.0
        assert row["score"] == 62.5
        assert row["rating"] == "Unsatisfactory"


@pytest.mark.django_db
class TestComplianceEndpoint:
    def test_supervisor_can_read_compliance(self, api_client, supervisor_role, report_officer_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        handler = UserFactory(role=report_officer_role, is_staff=True)
        _resolved_report(handler, validator_name="Engr. Dela Cruz")

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
