import pytest

from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from apps.accounts.tests.factories import UserFactory
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestLogReportSeverityChange:
    # Regression: this method used to reassign `actor = actor.user_number`,
    # turning the Users instance into a str, then read `actor.user_id` when
    # building the audit log -> AttributeError on the default (no override)
    # path. It had no test coverage, so the crash shipped unnoticed.

    def test_no_description_override_does_not_crash(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_report_severity_change(
            actor=actor,
            old_severity="P4",
            new_severity="P1",
            report=report,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE)
        assert log.user_id == actor.user_id
        assert "P4" in log.description and "P1" in log.description
        assert actor.user_number in log.description

    def test_generated_description_mentions_actor(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_report_severity_change(
            actor=actor,
            old_severity="P3",
            new_severity="P2",
            report=report,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE)
        assert actor.user_number in log.description

    def test_description_override_is_respected(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_report_severity_change(
            actor=actor,
            old_severity="P3",
            new_severity="P2",
            report=report,
            description_override="custom severity note",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE)
        assert log.description == "custom severity note"


@pytest.mark.django_db
class TestModerationActorRenaming:
    # Guard: the moderation log helpers were renamed from `user=` to `actor=`
    # to match every other audit-log helper. Calling with `user=` (the old
    # name) must fail; calling with `actor=` must log the correct actor.

    def test_log_warning_accepts_actor_kwarg(self):
        actor = UserFactory()
        warned = UserFactory()

        AuditLogService.log_warning(
            actor=actor,
            warned_user=warned,
            reason="Spamming the report feed.",
            warning_number="WARN-TEST-0001",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.WARNING)
        assert log.user_id == actor.user_id
        assert warned.user_number in log.description
        assert actor.user_number in log.description

    def test_log_ban_accepts_actor_kwarg(self):
        actor = UserFactory()
        banned = UserFactory()

        AuditLogService.log_ban(
            actor=actor,
            banned_user=banned,
            reason="Repeated harassment.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.BAN)
        assert log.user_id == actor.user_id
        assert banned.user_number in log.description
        assert actor.user_number in log.description

    def test_log_unban_accepts_actor_kwarg(self):
        actor = UserFactory()
        unbanned = UserFactory()

        AuditLogService.log_unban(
            actor=actor,
            unbanned_user=unbanned,
            reason="Appeal upheld.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UNBAN)
        assert log.user_id == actor.user_id
        assert unbanned.user_number in log.description
        assert actor.user_number in log.description

    def test_log_warning_rejects_old_user_kwarg(self):
        actor = UserFactory()
        warned = UserFactory()

        with pytest.raises(TypeError):
            AuditLogService.log_warning(
                user=actor,
                warned_user=warned,
                reason="Legacy kwarg.",
                warning_number="WARN-TEST-0002",
            )
