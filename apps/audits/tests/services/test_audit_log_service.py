from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from apps.audits.exceptions.audit_log_exception import AuditLogNotFoundException
from apps.accounts.models import Permissions
from apps.accounts.tests.factories import UserFactory, RoleFactory
from apps.reports.tests.factories import HazardReportFactory
from shared.authorization import AllPermissions


def _role_with(*permissions):
    # `sync_perms` already seeds every permission name (unique constraint),
    # so reuse the seeded row when it exists.
    permission_rows = [
        Permissions.objects.get_or_create(
            permission_name=permission.name,
            defaults={
                "description": permission.description,
                "module": permission.module,
            },
        )[0]
        for permission in permissions
    ]
    return RoleFactory(permissions=permission_rows)


def _seed_modules():
    """One USER-module (system) log by actor_a, one REPORT-module log by actor_b."""
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

    def test_payload_override_replaces_generated_payload(self):
        actor = UserFactory()
        report = HazardReportFactory()
        override = {"severity_change": {"from": "P4", "to": "P1"}, "extra": True}

        AuditLogService.log_report_severity_change(
            actor=actor,
            old_severity="P4",
            new_severity="P1",
            report=report,
            payload_override=override,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE)
        assert log.payload == override
        assert "severity was changed" in log.description


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


@pytest.mark.django_db
class TestLogCreate:
    def test_description_override_replaces_generated_description(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_create(
            actor=actor,
            module=AuditLogs.ModuleType.REPORT,
            target_object=report,
            target_identifier=report.report_number,
            payload={"initial_status": "New"},
            description_override="Custom creation note.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.CREATE)
        assert log.description == "Custom creation note."
        assert log.payload == {"initial_status": "New"}
        assert log.module == AuditLogs.ModuleType.REPORT
        assert log.user_id == actor.user_id

    def test_generated_description_names_module_and_actor(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_create(
            actor=actor,
            module=AuditLogs.ModuleType.REPORT,
            target_object=report,
            target_identifier=report.report_number,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.CREATE)
        assert (
            log.description
            == f"REPORT {report.report_number} was created by {actor.user_number}"
        )
        assert log.payload == {}


@pytest.mark.django_db
class TestLogDeactivateDefaultDescription:
    def test_user_target_without_reason(self):
        actor = UserFactory()
        target = UserFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=target,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert f"{target.user_number} ({target.role.role_name})" in log.description
        assert actor.user_number in log.description
        assert "reason" not in log.description
        assert log.payload == {}

    def test_user_target_appends_the_reason(self):
        actor = UserFactory()
        target = UserFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=target,
            reason="Dormant account.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert 'with the reason: "Dormant account."' in log.description

    def test_role_target_uses_the_role_code(self):
        actor = UserFactory()
        role = RoleFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.ROLE,
            target_object=role,
            reason="Unused role.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert role.role_code in log.description
        assert 'with the reason: "Unused role."' in log.description

    def test_description_override_short_circuits_generation(self):
        actor = UserFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=UserFactory(),
            description_override="Deactivated by bulk job.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.description == "Deactivated by bulk job."


@pytest.mark.django_db
class TestLogReportStatusChangeOverrides:
    def test_payload_and_description_overrides_win(self):
        actor = UserFactory()
        report = HazardReportFactory()
        override = {"status_change": {"from": "New", "to": "Assigned"}}

        AuditLogService.log_report_status_change(
            actor=actor,
            old_status="New",
            new_status="Assigned",
            remarks="   ",
            report=report,
            payload_override=override,
            description_override="Custom status note.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        assert log.payload == override
        assert log.description == "Custom status note."

    def test_payload_override_keeps_the_generated_description(self):
        actor = UserFactory()
        report = HazardReportFactory()
        override = {"status_change": {"from": "new", "to": "assigned"}}

        AuditLogService.log_report_status_change(
            actor=actor,
            old_status="new",
            new_status="assigned",
            report=report,
            payload_override=override,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        assert log.payload == override
        assert log.description == (
            f"REPORT {report.report_number} status was changed "
            f"from NEW to ASSIGNED by {actor.user_number}"
        )


@pytest.mark.django_db
class TestDescriptionTruncation:
    def test_short_description_is_left_unchanged(self):
        actor = UserFactory()
        warned = UserFactory()

        AuditLogService.log_warning(
            actor=actor,
            warned_user=warned,
            reason="Short reason.",
            warning_number="WARN-TEST-0003",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.WARNING)
        assert log.description == (
            f"{warned.user_number} was issued a warning by {actor.user_number}"
            f' with the reason: "Short reason."'
        )

    def test_long_description_is_cut_to_max_length_ending_with_ellipsis(self):
        actor = UserFactory()
        warned = UserFactory()
        reason = "R" * 400

        AuditLogService.log_warning(
            actor=actor,
            warned_user=warned,
            reason=reason,
            warning_number="WARN-TEST-0004",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.WARNING)
        max_length = AuditLogs._meta.get_field("description").max_length

        assert len(log.description) == max_length
        assert log.description.endswith("...")
        # The user-supplied text must still be fully recoverable from payload
        assert log.payload["reason"] == reason

    def test_long_status_remarks_are_truncated_but_kept_whole_in_payload(self):
        actor = UserFactory()
        remarks = "Needs DO 47 clearance. " * 20

        AuditLogService.log_report_status_change(
            actor=actor,
            old_status="Under Review",
            new_status="On-Hold",
            remarks=remarks,
            report=HazardReportFactory(),
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        max_length = AuditLogs._meta.get_field("description").max_length

        assert len(log.description) == max_length
        assert log.description.endswith("...")
        assert log.payload["remarks"] == remarks.strip()


@pytest.mark.django_db
class TestSeverityUnsetDisplay:
    def test_unset_old_severity_renders_unset_and_payload_keeps_none(self):
        actor = UserFactory()
        report = HazardReportFactory()

        AuditLogService.log_report_severity_change(
            actor=actor,
            old_severity=None,
            new_severity="P2",
            report=report,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.SEVERITY_CHANGE)
        assert f"from Unset to P2 by {actor.user_number}" in log.description
        assert "None" not in log.description
        assert log.payload["severity_change"] == {"from": None, "to": "P2"}


@pytest.mark.django_db
class TestLogDeactivateReasonPayload:
    def test_reason_is_kept_in_payload_without_description_override(self):
        actor = UserFactory()
        target = UserFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=target,
            reason="Dormant account.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.payload == {"reason": "Dormant account."}

    def test_reason_is_kept_in_payload_even_with_description_override(self):
        actor = UserFactory()
        target = UserFactory()

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=target,
            reason="Dormant account.",
            description_override="Deactivated by bulk job.",
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.payload == {"reason": "Dormant account."}
        assert log.description == "Deactivated by bulk job."

    def test_payload_override_is_not_mutated_in_place(self):
        actor = UserFactory()
        override = {"changes": {"is_active": {"from": True, "to": False}}}

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogs.ModuleType.USER,
            target_object=UserFactory(),
            reason="Dormant account.",
            payload_override=override,
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.payload == {
            "changes": {"is_active": {"from": True, "to": False}},
            "reason": "Dormant account.",
        }
        assert "reason" not in override


@pytest.mark.django_db
class TestListAuthorizedAuditLogs:
    def test_system_admin_sees_every_module(self, system_admin_role):
        system_log, report_log = _seed_modules()

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=system_admin_role),
            query_filters={},
        )

        assert {log.audit_log_number for log in result.value} == {
            system_log.audit_log_number,
            report_log.audit_log_number,
        }

    def test_system_logs_only_role_excludes_report_module(self):
        system_log, report_log = _seed_modules()
        user = UserFactory(role=_role_with(AllPermissions.AUDITS.READ_SYSTEM_LOGS))

        result = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={},
        )

        numbers = [log.audit_log_number for log in result.value]
        assert numbers == [system_log.audit_log_number]

    def test_report_logs_only_role_excludes_system_modules(self, supervisor_role):
        system_log, report_log = _seed_modules()

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=supervisor_role),
            query_filters={},
        )

        numbers = [log.audit_log_number for log in result.value]
        assert numbers == [report_log.audit_log_number]

    def test_role_without_audit_permissions_sees_nothing(self, report_officer_role):
        _seed_modules()

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=report_officer_role),
            query_filters={},
        )

        assert list(result.value) == []

    def test_module_filter_narrows_results(self, system_admin_role):
        system_log, report_log = _seed_modules()

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=system_admin_role),
            query_filters={"module": AuditLogs.ModuleType.REPORT.value},
        )

        numbers = [log.audit_log_number for log in result.value]
        assert numbers == [report_log.audit_log_number]

    def test_date_filters_include_and_exclude_logs(self, system_admin_role):
        _seed_modules()
        user = UserFactory(role=system_admin_role)
        today = timezone.now().date()

        included = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"from_date": today, "to_date": today},
        )
        excluded_from = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"from_date": today + timedelta(days=1)},
        )
        excluded_to = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"to_date": today - timedelta(days=1)},
        )

        assert len(included.value) == 2
        assert list(excluded_from.value) == []
        assert list(excluded_to.value) == []

    def test_role_id_zero_returns_only_system_actions(self, system_admin_role):
        AuditLogService.log_report_status_change(
            actor=None,
            old_status="New",
            new_status="Assigned",
            report=HazardReportFactory(),
        )
        _seed_modules()

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=system_admin_role),
            query_filters={"role_id": 0},
        )

        logs = list(result.value)
        assert len(logs) == 1
        assert logs[0].user_id is None

    def test_role_id_filters_by_the_actors_role(
        self, system_admin_role, report_officer_role
    ):
        officer = UserFactory(role=report_officer_role)
        AuditLogService.log_update(
            actor=officer,
            module=AuditLogs.ModuleType.USER,
            target_object=UserFactory(),
            description="Handled by the officer.",
        )
        AuditLogService.log_update(
            actor=UserFactory(),
            module=AuditLogs.ModuleType.USER,
            target_object=UserFactory(),
            description="Handled by someone else.",
        )

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=system_admin_role),
            query_filters={"role_id": report_officer_role.role_id},
        )

        logs = list(result.value)
        assert len(logs) == 1
        assert logs[0].user_id == officer.user_id

    def test_search_matches_log_number_or_actor_user_number(self, system_admin_role):
        system_log, report_log = _seed_modules()
        user = UserFactory(role=system_admin_role)

        by_log_number = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"q": system_log.audit_log_number},
        )
        by_user_number = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"q": report_log.user.user_number},
        )
        no_match = AuditLogService.list_authorized_audit_logs(
            user=user,
            query_filters={"q": "NOMATCH-XYZ"},
        )

        assert [log.audit_log_number for log in by_log_number.value] == [
            system_log.audit_log_number
        ]
        assert [log.audit_log_number for log in by_user_number.value] == [
            report_log.audit_log_number
        ]
        assert list(no_match.value) == []

    def test_results_are_ordered_newest_first(self, system_admin_role):
        system_log, report_log = _seed_modules()
        # Force deterministic timestamps: auto_now_add may land on the same
        # microsecond for back-to-back inserts.
        AuditLogs.objects.filter(pk=system_log.pk).update(
            created_at=timezone.now() - timedelta(hours=1)
        )

        result = AuditLogService.list_authorized_audit_logs(
            user=UserFactory(role=system_admin_role),
            query_filters={},
        )

        numbers = [log.audit_log_number for log in result.value]
        assert numbers == [report_log.audit_log_number, system_log.audit_log_number]


@pytest.mark.django_db
class TestGetAuthorizedAuditLog:
    def test_returns_the_matching_log(self, system_admin_role):
        system_log, _ = _seed_modules()

        result = AuditLogService.get_authorized_audit_log(
            user=UserFactory(role=system_admin_role),
            audit_log_number=system_log.audit_log_number,
        )

        assert result.value.audit_log_number == system_log.audit_log_number
        assert result.value.user is not None

    def test_lookup_is_case_insensitive(self, system_admin_role):
        system_log, _ = _seed_modules()

        result = AuditLogService.get_authorized_audit_log(
            user=UserFactory(role=system_admin_role),
            audit_log_number=system_log.audit_log_number.lower(),
        )

        assert result.value.pk == system_log.pk

    def test_unknown_log_number_raises_not_found(self, system_admin_role):
        _seed_modules()

        with pytest.raises(AuditLogNotFoundException):
            AuditLogService.get_authorized_audit_log(
                user=UserFactory(role=system_admin_role),
                audit_log_number="LOG-00000000-N0PE",
            )

    def test_logs_outside_the_users_modules_raise_not_found(self, supervisor_role):
        system_log, _ = _seed_modules()

        with pytest.raises(AuditLogNotFoundException):
            AuditLogService.get_authorized_audit_log(
                user=UserFactory(role=supervisor_role),
                audit_log_number=system_log.audit_log_number,
            )
