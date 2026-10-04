from rest_framework import serializers


class _ReportMetricsByStatus(serializers.Serializer):
    new = serializers.IntegerField(default=0)
    assigned = serializers.IntegerField(default=0)
    under_review = serializers.IntegerField(default=0)
    on_hold = serializers.IntegerField(default=0)
    dispatched = serializers.IntegerField(default=0)
    resolved = serializers.IntegerField(default=0)
    closed = serializers.IntegerField(default=0)


class GetReportMetricsResponseSerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    count_by_status = _ReportMetricsByStatus()
