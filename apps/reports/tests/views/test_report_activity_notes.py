import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestReportActivityNotes:
    @staticmethod
    def _officer_and_report(role, **report_kwargs):
        officer = UserFactory(role=role, is_staff=True)
        defaults = {
            "assigned_to": officer,
            "status": HazardReports.Status.IN_PROGRESS,
            "severity": "P2",
        }
        defaults.update(report_kwargs)
        return officer, HazardReportFactory(**defaults)

    def test_activity_note_does_not_change_status_but_writes_history(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "activity": "DISPATCHED",
                "activity_remarks": "Forwarded to the city engineering field team.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.remarks == "Forwarded to the city engineering field team."

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.ACTIVITY_NOTE)
        assert log.payload["activity_note"] == {
            "type": "DISPATCHED",
            "label": "Forwarded to field personnel",
            "status": "In Progress",
        }
        assert log.payload["remarks"] == "Forwarded to the city engineering field team."

    def test_activity_note_requires_its_own_remark(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"activity": "WORK_STARTED"},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "ACTIVITY_REMARKS_REQUIRED"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_activity_remarks_without_activity_are_rejected(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"activity_remarks": "No activity selected."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "ACTIVITY_REMARKS_WITHOUT_ACTIVITY"

    def test_validated_is_not_a_selectable_activity(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"activity": "VALIDATED", "activity_remarks": "Looks valid."},
            format="json",
        )

        assert response.status_code == 400
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_activity_note_is_rejected_before_handling_starts(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(
            report_officer_role, status=HazardReports.Status.ASSIGNED
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"activity": "DISPATCHED", "activity_remarks": "Forwarded too early."},
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "REPORT_ACTIVITY_NOT_PERMITTED"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ASSIGNED

    def test_activity_note_is_allowed_on_hold(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(
            report_officer_role, status=HazardReports.Status.ON_HOLD
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "activity": "REFERRED",
                "activity_remarks": "Referred to the barangay drainage office.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD
        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.ACTIVITY_NOTE
        ).count() == 1

    def test_referral_requires_on_hold(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "activity": "REFERRED",
                "activity_remarks": "Referred to the drainage office.",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "REFERRAL_REQUIRES_ON_HOLD"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_referral_cannot_be_logged_while_resuming_from_on_hold(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(
            report_officer_role, status=HazardReports.Status.ON_HOLD
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "IN_PROGRESS",
                "activity": "REFERRED",
                "activity_remarks": "Referred to the drainage office.",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "REFERRAL_REQUIRES_ON_HOLD"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD

    def test_referral_can_be_saved_with_the_on_hold_transition(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Waiting on the drainage office.",
                "activity": "REFERRED",
                "activity_remarks": "Referred to the barangay drainage office.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD

    def test_activity_can_accompany_the_assigned_to_in_progress_transition(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(
            report_officer_role,
            status=HazardReports.Status.ASSIGNED,
            severity=None,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "IN_PROGRESS",
                "severity": "P2",
                "activity": "NOTE",
                "activity_remarks": "Validated on site and forwarded for scheduling.",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.severity == "P2"
        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        ).count() == 1
        assert AuditLogs.objects.filter(
            action=AuditLogs.ActionType.ACTIVITY_NOTE
        ).count() == 1

    def test_status_and_activity_remarks_stay_separate(
        self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Waiting on the drainage office.",
                "activity": "REFERRED",
                "activity_remarks": "Referred to the barangay drainage office.",
            },
            format="json",
        )

        assert response.status_code == 200
        status_log = AuditLogs.objects.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        activity_log = AuditLogs.objects.get(action=AuditLogs.ActionType.ACTIVITY_NOTE)
        assert status_log.payload["remarks"] == "Waiting on the drainage office."
        assert activity_log.payload["remarks"] == "Referred to the barangay drainage office."
        assert activity_log.payload["activity_note"]["type"] == "REFERRED"

    def test_activity_is_rejected_when_resolving(self, api_client, report_officer_role):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "RESOLVED",
                "remarks": "Work completed.",
                "activity": "WORK_COMPLETED",
                "activity_remarks": "Completed on site.",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "REPORT_ACTIVITY_NOT_PERMITTED"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_citizen_timeline_exposes_activity_without_actor_identity(
        self, api_client, report_officer_role, citizen_role
    ):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            reported_by=citizen,
            assigned_to=officer,
            status=HazardReports.Status.IN_PROGRESS,
            severity="P2",
        )

        api_client.force_authenticate(user=officer)
        patch_response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "activity": "WORK_COMPLETED",
                "activity_remarks": "The pothole was patched and compacted.",
            },
            format="json",
        )
        assert patch_response.status_code == 200

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        activity_entries = [
            entry for entry in response.data["status_timeline"]
            if entry["action"] == "ACTIVITY_NOTE"
        ]
        assert len(activity_entries) == 1
        entry = activity_entries[0]
        assert entry["activity"] == "WORK_COMPLETED"
        assert entry["activity_label"] == "Corrective work completed"
        assert entry["status"] == "In Progress"
        assert entry["remarks"] == "The pothole was patched and compacted."
        assert entry["performed_by_role"] == report_officer_role.role_name

        # Activity entries remain citizen-safe: no staff identity leaks.
        assert officer.email not in str(response.data)
        assert officer.user_number not in str(response.data)
