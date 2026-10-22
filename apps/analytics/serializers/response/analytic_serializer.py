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


class _OverviewDaily(serializers.Serializer):
    date = serializers.CharField()
    count = serializers.IntegerField()


class _OverviewDailyTrend(serializers.Serializer):
    date = serializers.CharField()
    avg_days = serializers.FloatField()
    resolved = serializers.IntegerField()


class _OverviewWeekly(serializers.Serializer):
    week_start = serializers.CharField()
    avg_days = serializers.FloatField()
    resolved = serializers.IntegerField()


class _OverviewSlowest(serializers.Serializer):
    report_number = serializers.CharField()
    category = serializers.CharField()
    resolved_at = serializers.DateTimeField()
    days = serializers.FloatField()


class _OverviewIntake(serializers.Serializer):
    total = serializers.IntegerField()
    by_severity = serializers.DictField(child=serializers.IntegerField())
    by_status = serializers.DictField(child=serializers.IntegerField())
    daily = _OverviewDaily(many=True)


class _OverviewDelivery(serializers.Serializer):
    resolved = serializers.IntegerField()
    avg_days = serializers.FloatField(allow_null=True)
    daily = _OverviewDailyTrend(many=True)
    weekly = _OverviewWeekly(many=True)
    slowest = _OverviewSlowest(many=True)


class _OverviewSla(serializers.Serializer):
    on_time = serializers.IntegerField()
    late = serializers.IntegerField()
    breach = serializers.IntegerField()
    pending = serializers.IntegerField()
    judged = serializers.IntegerField()
    on_time_pct = serializers.FloatField(allow_null=True)


class _OverviewLive(serializers.Serializer):
    open = serializers.IntegerField()
    overdue = serializers.IntegerField()


class GetOverviewResponseSerializer(serializers.Serializer):
    # Plain dicts of YYYY-MM-DD strings ("from"/"to" are not usable as
    # Python field names without renaming the response keys).
    range = serializers.DictField()
    span = serializers.DictField()
    intake = _OverviewIntake()
    delivery = _OverviewDelivery()
    sla = _OverviewSla()
    live = _OverviewLive()


class HandlerWorkloadSerializer(serializers.Serializer):
    user_number = serializers.CharField()
    handler_name = serializers.CharField()
    handled = serializers.IntegerField()
    resolved = serializers.IntegerField()


class GetHandlerWorkloadResponseSerializer(serializers.Serializer):
    handlers = HandlerWorkloadSerializer(many=True)
