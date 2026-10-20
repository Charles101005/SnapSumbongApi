import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestEmployeeHandlersListView:
    def test_supervisor_sees_only_eligible_active_staff(
        self, api_client, supervisor_role, report_officer_role, system_admin_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        officer = UserFactory(role=report_officer_role, is_staff=True)
        inactive_officer = UserFactory(
            role=report_officer_role, is_staff=True, is_active=False
        )
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/accounts/employees/handlers/")

        assert response.status_code == 200
        user_numbers = [row["user_number"] for row in response.data["results"]]

        assert officer.user_number in user_numbers
        assert inactive_officer.user_number not in user_numbers
        assert admin.user_number not in user_numbers
        assert citizen.user_number not in user_numbers

    def test_admin_can_list_handlers(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=admin)
        response = api_client.get("/accounts/employees/handlers/")

        assert response.status_code == 200
        user_numbers = [row["user_number"] for row in response.data["results"]]
        assert officer.user_number in user_numbers

    def test_search_filters_handlers_by_name(
        self, api_client, supervisor_role, report_officer_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        matching = UserFactory(
            role=report_officer_role, is_staff=True, first_name="Transferable"
        )
        UserFactory(role=report_officer_role, is_staff=True, first_name="Someone")

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/accounts/employees/handlers/", {"q": "Transferable"})

        assert response.status_code == 200
        user_numbers = [row["user_number"] for row in response.data["results"]]
        assert user_numbers == [matching.user_number]

    def test_report_officer_cannot_list_handlers(
        self, api_client, report_officer_role
    ):
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=officer)
        response = api_client.get("/accounts/employees/handlers/")

        assert response.status_code == 403

    def test_citizen_cannot_list_handlers(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/accounts/employees/handlers/")

        assert response.status_code == 403
