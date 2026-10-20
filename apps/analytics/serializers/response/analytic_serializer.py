from rest_framework import serializers


class _ReportMetricsByStatus(serializers.Serializer):
    new = serializers.IntegerField(default=0)
    assigned = serializers.IntegerField(default=0)
    under_review = serializers.IntegerField(default=0)
    on_hold = serializers.IntegerField(default=0)
    dispatched = serializers.IntegerField(default=0)
    ongoing = serializers.IntegerField(default=0)
    resolved = serializers.IntegerField(default=0)
    closed = serializers.IntegerField(default=0)
    invalid = serializers.IntegerField(default=0)


class GetReportMetricsResponseSerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    count_by_status = _ReportMetricsByStatus()


class HandlerComplianceSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    handler_name = serializers.CharField()
    resolved_count = serializers.IntegerField()
    sla_on_time_pct = serializers.FloatField(allow_null=True)
    photolog_pct = serializers.FloatField(allow_null=True)
    validation_pct = serializers.FloatField(allow_null=True)
    score = serializers.FloatField(allow_null=True)
    rating = serializers.CharField()


class GetHandlerComplianceResponseSerializer(serializers.Serializer):
    weights = serializers.DictField(child=serializers.FloatField())
    handlers = HandlerComplianceSerializer(many=True)
