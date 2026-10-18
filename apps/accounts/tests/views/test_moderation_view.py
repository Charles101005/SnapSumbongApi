import pytest

from apps.accounts.models import CitizenWarnings
from apps.accounts.services.moderation_service import ModerationService
from apps.accounts.tests.factories import UserFactory


def _warn(citizen, actor, reason="Test warning reason for moderation."):
    return ModerationService.issue_warning(
        actor=actor,
        user_number=citizen.user_number,
        reason=reason,
    )


@pytest.mark.django_db
class TestWarnCitizenEndpoint:
    def test_supervisor_can_warn_via_endpoint(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/warn/",
            {"reason": "Repeated false hazard reports."},
            format="json",
        )

        assert response.status_code == 201
        assert CitizenWarnings.objects.filter(user=citizen).count() == 1

    def test_warn_unknown_user_returns_404(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            "/accounts/citizens/USER-99999999-XXXXXX/warn/",
            {"reason": "Targeting a user number that does not exist."},
            format="json",
        )

        assert response.status_code == 404
        assert response.data["error_code"] == "USER_NOT_FOUND"

    def test_warn_invalid_linked_report_returns_400(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/warn/",
            {
                "reason": "Citing a report number that does not exist.",
                "report_number": "RPT-99999999-XXXXXX",
            },
            format="json",
        )

        assert response.status_code == 404
        assert response.data["error_code"] == "USER_NOT_FOUND"


@pytest.mark.django_db
class TestBanCitizenEndpoint:
    def test_admin_can_ban_citizen_with_three_warnings(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        for _ in range(3):
            _warn(citizen, admin)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/ban/",
            {"reason": "Three strikes reached — account suspended."},
            format="json",
        )

        assert response.status_code == 200
        citizen.refresh_from_db()
        assert citizen.is_active is False

    def test_ban_not_eligible_returns_400(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/ban/",
            {"reason": "No warnings and no invalid report evidence."},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error_code"] == "BAN_NOT_ELIGIBLE"


@pytest.mark.django_db
class TestUnbanCitizenEndpoint:
    def test_admin_can_unban_banned_citizen(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_active=False)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/unban/",
            {"reason": "Ban lifted after successful appeal."},
            format="json",
        )

        assert response.status_code == 200
        citizen.refresh_from_db()
        assert citizen.is_active is True

    def test_unban_active_account_returns_409(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/accounts/citizens/{citizen.user_number}/unban/",
            {"reason": "Target account is not actually banned."},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["error_code"] == "UNBAN_TARGET_NOT_INACTIVE"


@pytest.mark.django_db
class TestMyWarningsView:
    def test_citizen_can_view_own_warnings(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        _warn(citizen, supervisor, reason="Own warning visible to citizen.")

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/accounts/profile/warnings/")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["warnings"][0]["reason"] == "Own warning visible to citizen."


@pytest.mark.django_db
class TestMyModerationSummaryView:
    def test_citizen_can_view_own_moderation_summary(self, api_client, supervisor_role, citizen_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        _warn(citizen, supervisor)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/accounts/profile/moderation/")

        assert response.status_code == 200
        assert response.data["warning_count"] == 1
        assert response.data["is_active"] is True
