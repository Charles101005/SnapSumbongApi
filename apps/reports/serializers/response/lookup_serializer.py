from rest_framework import serializers


class LookupReportResponseSerializer(serializers.Serializer):
    categories = serializers.SerializerMethodField()
    statuses = serializers.ListField(child=serializers.DictField())
    severities = serializers.ListField(child=serializers.CharField())

    def get_categories(self, obj):
        categories = [
            {
                "hazard_id": category.hazard_id,
                "hazard_name": category.hazard_name,
                # DO 47 §4.1 response time — the edit modal uses it to preview
                # the recalculated due date before a category change is saved.
                "response_time_days": category.response_time_days,
            }
            for category in obj["categories"]
        ]
        return categories

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("user")

        if not user or not user.is_staff:
            data.pop("severities", None)

        return data
