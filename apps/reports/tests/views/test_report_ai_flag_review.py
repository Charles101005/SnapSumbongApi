import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from apps.reports.models import HazardReports, ReportImages
from apps.reports.tests.factories import HazardReportFactory


FLAGGED_IMAGE = "https://res.cloudinary.com/demo/flagged.jpg"


@pytest.mark.django_db
class TestReportAiFlagReview:
    @staticmethod
    def _officer_and_report(role, **report_kwargs):
        officer = UserFactory(role=role, is_staff=True)
        defaults = {
            "assigned_to": officer,
            "status": HazardReports.Status.UNDER_REVIEW,
            "severity": "P2",
            "is_ai_flagged": True,
            "ai_flag_reasons": ["AI_GENERATED", "CONTEXT_MISMATCH"],
        }
        defaults.update(report_kwargs)
        report = HazardReportFactory(**defaults)
        ReportImages.objects.create(
            report=report,
            image_url=FLAGGED_IMAGE,
            photo_type=ReportImages.PhotoType.BEFORE,
            is_ai_flagged=True,
        )
        return officer, report

    def test_leaving_triage_requires_an_ai_review_decision(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "ON_HOLD", "remarks": "Referred to another office."},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "AI_FLAG_REVIEW_REQUIRED"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.is_ai_flagged is True
        assert report.images.get(image_url=FLAGGED_IMAGE).is_ai_flagged is True

    def test_cleared_decision_clears_report_and_image_flags(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Photo is a composite but the hazard is real.",
                "ai_flag_decision": "CLEARED",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD
        assert report.is_ai_flagged is False
        # The raw screening reasons stay on the report for the record.
        assert report.ai_flag_reasons == ["AI_GENERATED", "CONTEXT_MISMATCH"]
        assert report.images.get(image_url=FLAGGED_IMAGE).is_ai_flagged is False

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.AI_FLAG_REVIEW)
        assert log.user_id == officer.user_id
        assert log.payload["ai_flag_review"]["decision"] == "CLEARED"
        assert log.payload["ai_flag_review"]["reasons"] == [
            "AI_GENERATED",
            "CONTEXT_MISMATCH",
        ]
        assert log.payload["ai_flag_review"]["flagged_images"] == [
            {"image_url": FLAGGED_IMAGE}
        ]
        assert log.payload["ai_flag_review"]["status_change"] == {
            "from": "Under Review",
            "to": "On-Hold",
        }
        assert log.payload["remarks"] == "Photo is a composite but the hazard is real."

    def test_confirmed_decision_clears_flags_and_marks_the_report_invalid(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "INVALID",
                "remarks": "The photo is AI-generated and not a real hazard.",
                "ai_flag_decision": "CONFIRMED",
            },
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.INVALID
        assert report.is_ai_flagged is False
        assert report.images.get(image_url=FLAGGED_IMAGE).is_ai_flagged is False

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.AI_FLAG_REVIEW)
        assert log.payload["ai_flag_review"]["decision"] == "CONFIRMED"
        assert log.payload["ai_flag_review"]["status_change"] == {
            "from": "Under Review",
            "to": "Invalid",
        }

    def test_confirmed_decision_requires_invalid_status(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Referred to another office.",
                "ai_flag_decision": "CONFIRMED",
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "AI_FLAG_DECISION_STATUS_MISMATCH"
        report.refresh_from_db()
        assert report.is_ai_flagged is True

    def test_cleared_decision_cannot_mark_the_report_invalid(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "INVALID",
                "remarks": "Not a real hazard.",
                "ai_flag_decision": "CLEARED",
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "AI_FLAG_DECISION_STATUS_MISMATCH"

    def test_moving_assigned_report_to_under_review_keeps_the_flag_pending(
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
            {"status": "UNDER_REVIEW"},
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.is_ai_flagged is True
        assert report.images.get(image_url=FLAGGED_IMAGE).is_ai_flagged is True

    def test_decision_on_an_unflagged_report_is_rejected(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(
            report_officer_role,
            is_ai_flagged=False,
            ai_flag_reasons=[],
        )
        report.images.update(is_ai_flagged=False)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Referred to another office.",
                "ai_flag_decision": "CLEARED",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "AI_FLAG_REVIEW_UNAVAILABLE"

    def test_detection_and_review_appear_in_the_staff_timeline(
            self, api_client, report_officer_role
    ):
        officer, report = self._officer_and_report(report_officer_role)
        AuditLogService.log_report_ai_flag_detected(report=report)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Valid hazard despite the synthetic-looking photo.",
                "ai_flag_decision": "CLEARED",
            },
            format="json",
        )
        assert response.status_code == 200

        history = api_client.get(f"/reports/history/{report.report_number}/")
        assert history.status_code == 200
        entries = history.json()["status_timeline"]
        actions = [entry["action"] for entry in entries]

        assert "AI flag detected" in actions
        assert "AI flag reviewed" in actions

        detection = next(entry for entry in entries if entry["action_code"] == "AI_FLAG_DETECTED")
        assert "flagged by automatic AI screening" in detection["description"]
        assert "AI_GENERATED" in detection["description"]
        assert detection["performed_by"] == {"name": "System", "role": None}

        review = next(entry for entry in entries if entry["action_code"] == "AI_FLAG_REVIEW")
        assert "cleared as a valid report" in review["description"]
        assert review["status"] == "On-Hold"

        # The officer reviewed the flag as part of leaving triage, so the
        # timeline reads review -> new status, not the other way around.
        review_index = next(
            index for index, entry in enumerate(entries)
            if entry["action_code"] == "AI_FLAG_REVIEW"
        )
        status_change_index = next(
            index for index, entry in enumerate(entries)
            if entry["action_code"] == "STATUS_CHANGE"
        )
        assert review_index < status_change_index

    def test_citizen_timeline_never_includes_ai_flag_logs(
            self, api_client, citizen_role, report_officer_role
    ):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            reported_by=citizen,
            assigned_to=officer,
            status=HazardReports.Status.UNDER_REVIEW,
            severity="P2",
            is_ai_flagged=True,
            ai_flag_reasons=["AI_GENERATED"],
        )
        ReportImages.objects.create(
            report=report,
            image_url=FLAGGED_IMAGE,
            photo_type=ReportImages.PhotoType.BEFORE,
            is_ai_flagged=True,
        )
        AuditLogService.log_report_ai_flag_detected(report=report)

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {
                "status": "ON_HOLD",
                "remarks": "Referred to another office.",
                "ai_flag_decision": "CLEARED",
            },
            format="json",
        )
        assert response.status_code == 200

        api_client.force_authenticate(user=citizen)
        detail = api_client.get(f"/reports/{report.report_number}/")
        assert detail.status_code == 200
        assert "is_ai_flagged" not in detail.json()
        assert "image_ai_flags" not in detail.json()

        actions = [entry["action"] for entry in detail.json()["status_timeline"]]
        assert "AI_FLAG_DETECTED" not in actions
        assert "AI_FLAG_REVIEW" not in actions
