import pytest

from apps.accounts.models import CitizenWarnings
from apps.accounts.services.moderation_service import ModerationService
from apps.accounts.domain_errors.user_error import (
    UserNotFoundError,
    WarnTargetInactiveError,
    LinkedReportNotInvalidError,
    LinkedReportNotOwnedError,
    LinkedReportAlreadyWarnedError,
    BanTargetInactiveError,
    BanSelfDeniedError,
    BanNotEligibleError,
    FastTrackReportNotInvalidError,
    FastTrackReportNotOwnedError,
    UnbanTargetNotInactiveError,
)
from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _warn(citizen, actor, reason="Test warning reason for moderation.", report=None):
    return ModerationService.issue_warning(
        actor=actor,
        user_number=citizen.user_number,
        reason=reason,
        report_number=report.report_number if report else None,
    )


@pytest.mark.django_db
class TestIssueWarning:
    def test_supervisor_can_warn_citizen(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        result = _warn(citizen, supervisor)

        assert result.is_success
        assert CitizenWarnings.objects.filter(user=citizen).count() == 1

    def test_warning_writes_audit_log(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        _warn(citizen, supervisor)

        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.WARNING,
            user=supervisor,
        ).exists()

    def test_warn_linked_invalid_report(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=citizen,
        )

        result = _warn(citizen, supervisor, report=report)

        assert result.is_success
        warning = CitizenWarnings.objects.get(user=citizen)
        assert warning.report == report

    def test_warn_rejects_non_invalid_report(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            reported_by=citizen,
        )

        result = _warn(citizen, supervisor, report=report)

        assert not result.is_success
        assert result.error == LinkedReportNotInvalidError

    def test_warn_rejects_report_not_owned(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        other_citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=other_citizen,
        )

        result = _warn(citizen, supervisor, report=report)

        assert not result.is_success
        assert result.error == LinkedReportNotOwnedError

    def test_warn_rejects_duplicate_report(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=citizen,
        )

        first = _warn(citizen, supervisor, report=report)
        second = _warn(citizen, supervisor, report=report)

        assert first.is_success
        assert not second.is_success
        assert second.error == LinkedReportAlreadyWarnedError
        assert CitizenWarnings.objects.filter(user=citizen).count() == 1

    def test_warn_allows_second_warning_on_different_report(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        first_report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=citizen,
        )
        second_report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=citizen,
        )

        first = _warn(citizen, supervisor, report=first_report)
        second = _warn(citizen, supervisor, report=second_report)

        assert first.is_success
        assert second.is_success
        assert CitizenWarnings.objects.filter(user=citizen).count() == 2

    def test_warn_rejects_inactive_target(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_active=False)

        result = _warn(citizen, supervisor)

        assert not result.is_success
        assert result.error == WarnTargetInactiveError

    def test_warn_rejects_unknown_user(self, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        result = ModerationService.issue_warning(
            actor=supervisor,
            user_number="USER-99999999-XXXXXX",
            reason="Test reason for unknown user.",
        )

        assert not result.is_success
        assert result.error == UserNotFoundError


@pytest.mark.django_db
class TestBanCitizen:
    def test_ban_with_three_warnings(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        for _ in range(3):
            _warn(citizen, admin)

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Three false reports — repeated misuse of the system.",
        )

        assert result.is_success
        citizen.refresh_from_db()
        assert citizen.is_active is False

    def test_ban_writes_audit_log(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        for _ in range(3):
            _warn(citizen, admin)

        ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Three strikes reached.",
        )

        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.BAN,
            user=admin,
        ).exists()

    def test_fast_track_ban_with_invalid_report(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=citizen,
        )

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Severe abuse — explicit content in report.",
            report_number=report.report_number,
        )

        assert result.is_success
        citizen.refresh_from_db()
        assert citizen.is_active is False

    def test_ban_rejected_with_no_warnings_no_report(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="No warnings and no evidence provided.",
        )

        assert not result.is_success
        assert result.error == BanNotEligibleError

    def test_ban_rejected_non_invalid_fast_track(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            reported_by=citizen,
        )

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Trying to ban with non-invalid report.",
            report_number=report.report_number,
        )

        assert not result.is_success
        assert result.error == FastTrackReportNotInvalidError

    def test_ban_rejected_fast_track_not_owned(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        other_citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            reported_by=other_citizen,
        )

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Trying to ban with another citizen's report.",
            report_number=report.report_number,
        )

        assert not result.is_success
        assert result.error == FastTrackReportNotOwnedError

    def test_self_ban_rejected(self, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)

        # Admins are staff; _find_citizen only matches is_staff=False,
        # so targeting your own user_number returns UserNotFound.
        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=admin.user_number,
            reason="Trying to ban self.",
        )

        assert not result.is_success
        assert result.error == UserNotFoundError

    def test_ban_already_banned_rejected(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_active=False)

        result = ModerationService.ban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Already banned account.",
        )

        assert not result.is_success
        assert result.error == BanTargetInactiveError


@pytest.mark.django_db
class TestUnbanCitizen:
    def test_unban_banned_citizen(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_active=False)

        result = ModerationService.unban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="False positive — defect verified real.",
        )

        assert result.is_success
        citizen.refresh_from_db()
        assert citizen.is_active is True

    def test_unban_writes_audit_log(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_active=False)

        ModerationService.unban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Reversing mistaken ban.",
        )

        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.UNBAN,
            user=admin,
        ).exists()

    def test_unban_active_account_rejected(self, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        result = ModerationService.unban_citizen(
            actor=admin,
            user_number=citizen.user_number,
            reason="Trying to unban active account.",
        )

        assert not result.is_success
        assert result.error == UnbanTargetNotInactiveError


@pytest.mark.django_db
class TestGetCitizenWarnings:
    def test_returns_warning_list_and_count(self, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        _warn(citizen, supervisor, reason="First warning reason here.")
        _warn(citizen, supervisor, reason="Second warning reason here.")

        result = ModerationService.get_citizen_warnings(user=citizen)

        assert result.is_success
        assert result.value["count"] == 2
        assert len(result.value["warnings"]) == 2

    def test_empty_warnings(self, citizen_role):
        citizen = UserFactory(role=citizen_role)

        result = ModerationService.get_citizen_warnings(user=citizen)

        assert result.is_success
        assert result.value["count"] == 0
        assert result.value["warnings"] == []


@pytest.mark.django_db
class TestBanEndpointPermissions:
    def test_cannot_ban_without_permission(self, api_client, citizen_role, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/ban/",
            {"reason": "Supervisor should not be able to ban accounts."},
            format="json",
        )

        assert response.status_code == 403

    def test_cannot_warn_without_permission(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        target = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.post(
            f"/accounts/citizens/{target.user_number}/warn/",
            {"reason": "Citizens should not be able to warn other citizens."},
            format="json",
        )

        assert response.status_code == 403

    def test_ban_endpoint_requires_reason_min_length(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        for _ in range(3):
            _warn(citizen, admin)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/ban/",
            {"reason": "short"},
            format="json",
        )

        assert response.status_code == 400

    def test_staff_can_read_citizen_warnings(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        _warn(citizen, supervisor, reason="First staff-visible warning.")

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(f"/accounts/citizens/{citizen.user_number}/warnings/")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["warnings"][0]["reason"] == "First staff-visible warning."

    def test_citizen_cannot_read_other_warnings(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/accounts/citizens/{other.user_number}/warnings/")

        assert response.status_code == 403


@pytest.mark.django_db
class TestSupervisorModerationWithoutUserManagement:
    def test_supervisor_cannot_list_citizens(self, api_client, supervisor_role, citizen_role):
        UserFactory(role=citizen_role)
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/accounts/citizens/")

        assert response.status_code == 403

    def test_supervisor_can_read_citizen_detail_for_moderation(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get(f"/accounts/citizens/{citizen.user_number}/")

        assert response.status_code == 200
        assert response.data["user_number"] == citizen.user_number
