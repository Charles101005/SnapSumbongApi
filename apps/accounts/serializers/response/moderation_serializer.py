from rest_framework import serializers


class _WarningRecordResponseSerializer(serializers.Serializer):
    warning_number = serializers.CharField()
    reason = serializers.CharField()
    report_number = serializers.CharField(allow_null=True)
    warned_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class CitizenWarningsResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    warnings = _WarningRecordResponseSerializer(many=True)


class ModerationSummaryResponseSerializer(serializers.Serializer):
    warning_count = serializers.IntegerField()
    is_active = serializers.BooleanField()
