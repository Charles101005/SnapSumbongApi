from rest_framework import serializers


class _ReportMetricsByStatus(serializers.Serializer):
    resolved = serializers.IntegerField(default=0)
    under_review = serializers.IntegerField(default=0)
    dispatched = serializers.IntegerField(default=0)


class GetReportMetricsResponseSerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    count_by_status = _ReportMetricsByStatus()
