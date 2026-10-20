import json

import pytest

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestCitizenTimelineDetail:
    """The citizen detail's status_timeline backs the clickable
    "View Details" dialog on the My Reports resolution timeline."""

    CITIZEN_SAFE_KEYS = {
        "status",
        "created_at",
        "action",
        "from_status",
        "to_status",
        "remarks",
        "performed_by_role",
    }

    @staticmethod
    def _citizen_viewing_a_report_flagged_invalid(api_client, citizen_role, report_officer_role, remarks):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        patch_response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "INVALID", "remarks": remarks},
            format="json",
        )
        assert patch_response.status_code == 200

        api_client.force_authenticate(user=reporter)
        detail_response = api_client.get(f"/reports/{report.report_number}/")
        assert detail_response.status_code == 200
        return detail_response, officer

    def test_timeline_entry_carries_the_status_change_details(self, api_client, citizen_role, report_officer_role):
        remarks = "Obvious fake report."
        response, _officer = self._citizen_viewing_a_report_flagged_invalid(
            api_client, citizen_role, report_officer_role, remarks
        )

        timeline = response.data["status_timeline"]
        assert timeline

        entry = timeline[-1]
        assert entry["status"] == "Invalid"
        assert entry["action"] == "STATUS_CHANGE"
        assert entry["from_status"] == "Under Review"
        assert entry["to_status"] == "Invalid"
        assert entry["remarks"] == remarks
        assert entry["performed_by_role"] == report_officer_role.role_name
        assert entry["created_at"]

    def test_timeline_never_leaks_the_actor_identity(self, api_client, citizen_role, report_officer_role):
        response, officer = self._citizen_viewing_a_report_flagged_invalid(
            api_client, citizen_role, report_officer_role, "Obvious fake report."
        )

        timeline = response.data["status_timeline"]
        for entry in timeline:
            assert set(entry) == self.CITIZEN_SAFE_KEYS
            # Role only: no name/email objects for the performing officer.
            assert isinstance(entry["performed_by_role"], str)

        serialized = json.dumps(response.data)
        assert officer.email not in serialized
        assert officer.user_number not in serialized

    def test_staff_detail_still_omits_status_timeline(self, api_client, citizen_role, report_officer_role):
        response, officer = self._citizen_viewing_a_report_flagged_invalid(
            api_client, citizen_role, report_officer_role, "Obvious fake report."
        )
        assert "status_timeline" in response.data

        api_client.force_authenticate(user=officer)
        staff_response = api_client.get(f"/reports/{response.data['report_number']}/")

        assert staff_response.status_code == 200
        assert "status_timeline" not in staff_response.data
