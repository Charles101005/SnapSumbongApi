import factory
from factory.django import DjangoModelFactory

from apps.audits.models import AuditLogs


class AuditLogFactory(DjangoModelFactory):
    """Audit log factory. The seeder passes actor, action, module,
    description, payload and target_object for each event."""

    class Meta:
        model = AuditLogs

    payload = factory.LazyFunction(dict)
    description = None
