from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import ValidatorNameRequiredError
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _resolve_images():
    return [
        {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
        {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
    ]


def _resolve(user, report, remarks="Pothole patched and compacted.", validated_by_name="Engr. Dela Cruz"):
    return ReportService.update_authorized_assigned_report(
        user=user,
        report_number=report.report_number,
        new_status_str=HazardReports.Status.RESOLVED,
        remarks=remarks,
        resolution_images=_resolve_images(),
        validated_by_name=validated_by_name,
    )


@pytest.mark.django_db
class TestDeclaredValidator:
    def _assigned_report(self):
        return HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            due_at=timezone.now() + timedelta(days=2),
        )

    def test_assignee_can_resolve_with_declared_validator(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report, validated_by_name="Engr. Dela Cruz")

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.validated_by_name == "Engr. Dela Cruz"
        assert report.validated_by_id == officer.user_id
        assert report.resolved_at is not None

    def test_resolving_requires_validator_name(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report, validated_by_name=None)

        assert result.is_success is False
        assert result.error is ValidatorNameRequiredError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED
        assert report.validated_by_name is None
        assert report.validated_by_id is None
        assert report.resolved_at is None

    def test_blank_validator_name_is_rejected(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report, validated_by_name="   ")

        assert result.is_success is False
        assert result.error is ValidatorNameRequiredError

    def test_validator_name_is_stripped(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report, validated_by_name="  Engr. Dela Cruz  ")

        assert result.is_success
        report.refresh_from_db()
        assert report.validated_by_name == "Engr. Dela Cruz"

    def test_any_name_is_accepted_including_handlers_own(self, report_officer_role):
        # The validator field is a pure declaration — no same-name guard.
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report, validated_by_name="Juan Dela Cruz")

        assert result.is_success
        report.refresh_from_db()
        assert report.validated_by_name == "Juan Dela Cruz"

    def test_different_staff_member_can_also_resolve(self, report_officer_role, supervisor_role):
        assignee = UserFactory(role=report_officer_role, is_staff=True)
        resolver = UserFactory(role=supervisor_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = assignee
        report.save(update_fields=["assigned_to"])

        result = _resolve(resolver, report, validated_by_name="Engr. Santos")

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.validated_by_name == "Engr. Santos"
        assert report.validated_by_id == resolver.user_id
