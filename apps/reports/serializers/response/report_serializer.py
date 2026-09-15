from decimal import Decimal

from rest_framework import serializers


class _ImageSignatureSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    signature = serializers.CharField()


class ReportImageSignatureResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    upload_url = serializers.URLField()
    upload_preset = serializers.CharField()
    asset_folder = serializers.CharField()
    use_asset_folder_as_public_id_prefix = serializers.BooleanField()
    timestamp = serializers.IntegerField()
    image_signatures = _ImageSignatureSerializer(many=True)


class CreateReportResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    reported_by = serializers.CharField()
    created_at = serializers.DateTimeField()


class GetReportListResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    category = serializers.SerializerMethodField()
    status = serializers.CharField(max_length=20)
    created_at = serializers.DateTimeField()

    def get_category(self, value) -> list:
        return value.category.hazard_name


class GetReportDetailResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    status = serializers.CharField(max_length=20)

    latitude = serializers.DecimalField(
        max_digits=8,
        decimal_places=6,
        min_value=Decimal('-90.0'),
        max_value=Decimal('90.0')
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal('-180.0'),
        max_value=Decimal('180.0')
    )

    address = serializers.CharField(max_length=255)
    description = serializers.CharField()

    image_urls = serializers.SerializerMethodField()
    status_timeline = serializers.SerializerMethodField()

    def get_image_urls(self, value) -> list:
        return [image.image_url for image in value.images.all()]

    def get_status_timeline(self, value) -> list:
        status_timeline = []

        for audit_log in value.audit_logs.all():
            payload = audit_log.payload

            if payload.get("initial_status"):
                status_timeline.append({
                    "status": payload["initial_status"],
                    "created_at": audit_log.created_at.isoformat(),
                })
                continue

            status_timeline.append({
                "status": payload["status_change"]["to"],
                "created_at": audit_log.created_at.isoformat(),
            })
        return status_timeline
