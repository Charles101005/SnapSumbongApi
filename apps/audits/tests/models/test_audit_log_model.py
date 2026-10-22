import pytest

from apps.audits.models import AuditLogs
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestAuditLogNumberAssignment:
    @staticmethod
    def _log(**overrides):
        defaults = {
            "action": AuditLogs.ActionType.CREATE,
            "module": AuditLogs.ModuleType.USER,
            "description": "Created for the test.",
            "payload": {},
            "target_object": UserFactory(),
        }
        defaults.update(overrides)
        return AuditLogs(**defaults)

    def test_number_is_generated_with_the_log_prefix(self):
        log = self._log()
        log.save()

        assert log.audit_log_number.startswith("LOG-")
        assert len(log.audit_log_number) <= 20

    def test_a_provided_number_is_preserved(self):
        log = self._log(audit_log_number="LOG-20240101-PRESET")
        log.save()

        assert log.audit_log_number == "LOG-20240101-PRESET"

    def test_a_collision_regenerates_the_number(self, mocker):
        taken = self._log()
        taken.save()

        generator = mocker.patch(
            "apps.audits.models.audit_log_model.model_number_generator",
            side_effect=[taken.audit_log_number, "LOG-20240101-FRESH1"],
        )
        log = self._log()
        log.save()

        assert generator.call_count == 2
        assert log.audit_log_number == "LOG-20240101-FRESH1"
        assert AuditLogs.objects.filter(audit_log_number="LOG-20240101-FRESH1").exists()
