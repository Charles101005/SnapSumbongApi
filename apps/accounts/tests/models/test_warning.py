import pytest

from apps.accounts.models import CitizenWarnings
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestCitizenWarningNumberGeneration:
    def test_save_generates_warning_number(self, citizen_role):
        user = UserFactory(role=citizen_role)

        warning = CitizenWarnings.objects.create(user=user, reason="Auto-generated number check.")

        prefix, date_str, suffix = warning.warning_number.split("-")
        assert prefix == "WARN"
        assert len(date_str) == 8
        assert len(suffix) == 6

    def test_explicit_warning_number_is_preserved(self, citizen_role):
        user = UserFactory(role=citizen_role)

        warning = CitizenWarnings.objects.create(
            user=user,
            warning_number="WARN-20250101-ABCDEF",
            reason="Explicit number must not be overwritten.",
        )

        assert warning.warning_number == "WARN-20250101-ABCDEF"

    def test_duplicate_warning_number_is_regenerated(self, citizen_role, mocker):
        user = UserFactory(role=citizen_role)
        existing = CitizenWarnings.objects.create(user=user, reason="First warning.")
        mocker.patch(
            "apps.accounts.models.warning_model.model_number_generator",
            side_effect=[existing.warning_number, "WARN-20991231-UNIQUE"],
        )

        warning = CitizenWarnings.objects.create(user=user, reason="Second warning.")

        assert warning.warning_number == "WARN-20991231-UNIQUE"
