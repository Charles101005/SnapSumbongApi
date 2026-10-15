from rest_framework import serializers

from apps.audits.services import AuditLogService


class ListAuditLogRequestSerializer(serializers.Serializer):
    q = serializers.CharField(required=False)
    module = serializers.ChoiceField(choices=AuditLogService.ModuleType.choices, required=False)
    role_id = serializers.IntegerField(required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

