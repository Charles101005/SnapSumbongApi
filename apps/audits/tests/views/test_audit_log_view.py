import pytest

from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from apps.accounts.tests.factories import UserFactory
from apps.reports.tests.factories import HazardReportFactory


def _seed_audit_logs():
    """One USER-module (system) log and one REPORT-module log."""
    actor_a = UserFactory()
    actor_b = UserFactory()

    AuditLogService.log_update(
        actor=actor_a,
        module=AuditLogs.ModuleType.USER,
        target_object=UserFactory(),
        description="User account updated.",
    )
    AuditLogService.log_report_severity_change(
        actor=actor_b,
        old_severity="P4",
        new_severity="P1",
        report=HazardReportFactory(),
    )

    return (
        AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE),
        AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE),
    )


@pytest.mark.django_db
class TestAuditLogListView:
    def test_system_admin_lists_every_module(self, api_client, system_admin_role):
        system_log, report_log = _seed_audit_logs()
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total_pages"] == 1
        assert {row["audit_log_number"] for row in data["results"]} == {
            system_log.audit_log_number,
            report_log.audit_log_number,
        }

    def test_supervisor_sees_only_report_logs(self, api_client, supervisor_role):
        system_log, report_log = _seed_audit_logs()
        user = UserFactory(role=supervisor_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["audit_log_number"] == report_log.audit_log_number
        assert data["results"][0]["module"] == "Report"

    def test_module_filter_is_applied(self, api_client, system_admin_role):
        _seed_audit_logs()
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/", {"module": "REPORT"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["module"] == "Report"

    def test_unknown_module_filter_returns_400(self, api_client, system_admin_role):
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/", {"module": "NOT_A_MODULE"})

        assert response.status_code == 400

    def test_role_without_audit_permissions_is_denied(
        self, api_client, report_officer_role
    ):
        _seed_audit_logs()
        user = UserFactory(role=report_officer_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/")

        assert response.status_code == 403


@pytest.mark.django_db
class TestAuditLogDetailView:
    def test_detail_returns_the_full_log(self, api_client, system_admin_role):
        system_log, _ = _seed_audit_logs()
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/audits/{system_log.audit_log_number}/")

        assert response.status_code == 200
        data = response.json()
        assert data["audit_log_number"] == system_log.audit_log_number
        assert data["description"] == "User account updated."
        assert data["payload"] == {}
        assert data["actor_name"]
        assert data["actor_role"]

    def test_system_action_shows_the_system_actor_placeholder(
        self, api_client, system_admin_role
    ):
        AuditLogService.log_report_status_change(
            actor=None,
            old_status="New",
            new_status="Assigned",
            report=HazardReportFactory(),
        )
        system_log = AuditLogs.objects.get(user__isnull=True)
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/audits/{system_log.audit_log_number}/")

        assert response.status_code == 200
        data = response.json()
        assert data["actor_name"] == "System"
        assert data["actor_role"] == "System"

    def test_unknown_log_returns_404(self, api_client, system_admin_role):
        _seed_audit_logs()
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/LOG-00000000-NOPE00/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "AUDIT_LOG_NOT_FOUND"

    def test_supervisor_cannot_open_system_logs(self, api_client, supervisor_role):
        system_log, _ = _seed_audit_logs()
        user = UserFactory(role=supervisor_role)

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/audits/{system_log.audit_log_number}/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "AUDIT_LOG_NOT_FOUND"

    def test_role_without_audit_permissions_is_denied(
        self, api_client, report_officer_role
    ):
        system_log, _ = _seed_audit_logs()
        user = UserFactory(role=report_officer_role)

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/audits/{system_log.audit_log_number}/")

        assert response.status_code == 403
