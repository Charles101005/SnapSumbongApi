import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardCategoryFactory


@pytest.mark.django_db
class TestReportLookupView:
    def test_staff_lookup_includes_severities(self, api_client, supervisor_role):
        category = HazardCategoryFactory(hazard_name="Road Crack")
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/reports/lookup/")

        assert response.status_code == 200
        data = response.json()
        assert data["categories"] == [
            {"hazard_id": category.hazard_id, "hazard_name": "Road Crack"}
        ]
        assert {
            "label": HazardReports.Status.NEW.label,
            "value": HazardReports.Status.NEW.value,
        } in data["statuses"]
        assert data["severities"] == [
            severity.value for severity in HazardReports.Severity
        ]

    def test_citizen_lookup_drops_severities(self, api_client, citizen_role):
        category = HazardCategoryFactory(hazard_name="Flooded Street")
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/reports/lookup/")

        assert response.status_code == 200
        data = response.json()
        assert "severities" not in data
        assert data["categories"] == [
            {"hazard_id": category.hazard_id, "hazard_name": "Flooded Street"}
        ]
        assert data["statuses"]


@pytest.mark.django_db
class TestHazardCategoryListView:
    def test_lists_every_hazard_category(self, api_client, citizen_role):
        category = HazardCategoryFactory(hazard_name="Flooded Street")
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/reports/hazard-category/")

        assert response.status_code == 200
        assert response.json() == [
            {
                "hazard_id": category.hazard_id,
                "hazard_name": "Flooded Street",
                "description": category.description,
            }
        ]
