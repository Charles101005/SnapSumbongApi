from rest_framework import serializers


class LookupFilterCitizenReportResponseSerializer(serializers.Serializer):
    categories = serializers.SerializerMethodField()
    statuses = serializers.ListField(child=serializers.CharField())

    def get_categories(self, obj):
        categories = [
            {
                "hazard_id": category.hazard_id,
                "hazard_name": category.hazard_name,
            }
            for category in obj["categories"]
        ]
        return categories