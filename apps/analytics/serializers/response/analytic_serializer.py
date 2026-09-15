from rest_framework import serializers


class _ReportMetricsByStatus(serializers.Serializer):
    resolved = serializers.IntegerField(default=0)
    in_progress = serializers.IntegerField(default=0)
    pending = serializers.IntegerField(default=0)


class GetReportMetricsResponseSerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    count_by_status = _ReportMetricsByStatus()
