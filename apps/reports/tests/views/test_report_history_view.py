import pytest

from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports, ReportImages
from apps.reports.tests.factories import HazardReportFactory


def _display_name(user):
    middle = f" {user.middle_name[0].upper()}." if user.middle_name else ""
    return f"{user.last_name}, {user.first_name}{middle}"


@pytest.mark.django_db
class TestReportHistoryDetailView:
    """The staff "View History" dialog renders one entry per audit log:
    the creation, every status change, and every transfer."""

    @staticmethod
    def _seed_history(officer_role):
        reporter = UserFactory()
        officer = UserFactory(role=officer_role, is_staff=True)
        new_officer = UserFactory(role=officer_role, is_staff=True)
        report = HazardReportFactory(
            assigned_to=officer,
            status=HazardReports.Status.UNDER_REVIEW,
            severity="P2",
            is_anonymous=True,
        )

        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/before.jpg",
            photo_type=ReportImages.PhotoType.BEFORE,
        )
        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/during.jpg",
            photo_type=ReportImages.PhotoType.DURING,
        )
        ReportImages.objects.create(
            report=report,
            image_url="https://res.cloudinary.com/demo/after.jpg",
            photo_type=ReportImages.PhotoType.AFTER,
        )

        AuditLogService.log_create(
            actor=reporter,
            module=AuditLogs.ModuleType.REPORT,
            target_object=report,
            target_identifier=report.report_number,
            payload={"initial_status": "New", "assigned_to": None},
        )
        AuditLogService.log_report_status_change(
            actor=officer,
            old_status="New",
            new_status="Under Review",
            remarks="Triaged.",
            report=report,
            payload_override={
                "status_change": {"from": "New", "to": "Under Review"},
                "remarks": "Triaged.",
            },
            description_override="Report triaged.",
        )
        AuditLogService.log_report_transfer(
            actor=officer,
            previous_assignee=None,
            new_assignee=new_officer,
            remarks="Reassigned to the field crew.",
            report=report,
        )
        AuditLogService.log_report_status_change(
            actor=None,
            old_status="Under Review",
            new_status="Dispatched",
            report=report,
            payload_override={
                "status_change": {"from": "Under Review", "to": "Dispatched"}
            },
            description_override="Auto-dispatched by scheduler.",
        )
        return report, officer, reporter

    def test_history_lists_every_timeline_entry(
        self, api_client, report_officer_role
    ):
        report, officer, reporter = self._seed_history(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/history/{report.report_number}/")

        assert response.status_code == 200
        data = response.json()

        assert data["report_number"] == report.report_number
        assert data["status"] == HazardReports.Status.UNDER_REVIEW.label
        assert data["category"] == report.category.hazard_name
        assert data["image_urls"] == [
            "https://res.cloudinary.com/demo/before.jpg"
        ]
        assert sorted(data["resolution_image_urls"]) == [
            "https://res.cloudinary.com/demo/after.jpg",
            "https://res.cloudinary.com/demo/during.jpg",
        ]

        entries = data["status_timeline"]
        assert [entry["action"] for entry in entries] == [
            "Created",
            "Status changed",
            "Report transferred",
            "Status changed",
        ]

        # Creation: a non-staff actor on an anonymous report stays anonymous.
        assert entries[0]["performed_by"] == {
            "name": "<Anonymous>",
            "role": reporter.role.role_name,
        }
        assert entries[0]["status"] == "New"

        assert entries[1]["performed_by"] == {
            "name": _display_name(officer),
            "role": officer.role.role_name,
        }
        assert entries[1]["status"] == "Under Review"
        assert entries[1]["module"] == "Report Management"
        assert entries[1]["description"] == "Report triaged."

        # TRANSFER payloads carry an assignment_change instead of a status
        # change, so the entry falls back to the report's current status.
        assert entries[2]["status"] == HazardReports.Status(report.status).label
        assert entries[2]["performed_by"]["name"] == _display_name(officer)

        # The automated assignment sweep logs with no actor at all.
        assert entries[3]["performed_by"] == {"name": "System", "role": None}
        assert entries[3]["status"] == "Dispatched"

    def test_role_without_history_permission_is_denied(
        self, api_client, citizen_role
    ):
        report, _, _ = self._seed_history(citizen_role)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/history/{report.report_number}/")

        assert response.status_code == 403
