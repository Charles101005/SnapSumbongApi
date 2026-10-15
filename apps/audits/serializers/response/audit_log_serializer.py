from rest_framework import serializers


class ListAuditLogResponseSerializer(serializers.Serializer):
    audit_log_number = serializers.CharField()
    actor_name = serializers.CharField(source='user.get_full_name', default="System")
    actor_role = serializers.CharField(source='user.role.role_name', default="System")
    action = serializers.CharField(source='get_action_display')
    module = serializers.CharField(source='get_module_display')
    created_at = serializers.DateTimeField()


class DetailAuditLogResponseSerializer(serializers.Serializer):
    audit_log_number = serializers.CharField()
    actor_name = serializers.CharField(source='user.get_full_name', default="System")
    actor_role = serializers.CharField(source='user.role.role_name', default="System")
    action = serializers.CharField(source='get_action_display')
    module = serializers.CharField(source='get_module_display')
    description = serializers.CharField()
    payload = serializers.JSONField()
    created_at = serializers.DateTimeField()