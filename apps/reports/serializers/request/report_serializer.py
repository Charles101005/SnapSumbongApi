from decimal import Decimal

from rest_framework import serializers
from django.conf import settings

from external.storage import StorageService, UploadIntent


class ReportImageSignatureRequestSerializer(serializers.Serializer):
    image_count = serializers.IntegerField(
        min_value=1,
        max_value=settings.STORAGE_CONFIG['MAX_SIGNATURE_COUNT']
    )


class CreateReportRequestSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
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
    address = serializers.CharField(min_length=10, max_length=255)
    description = serializers.CharField(min_length=5)
    is_anonymous = serializers.BooleanField(default=False)

    image_urls = serializers.ListField(
        child=serializers.URLField(max_length=500),
        min_length=1,
        max_length=settings.STORAGE_CONFIG['MAX_SIGNATURE_COUNT']
    )

    def validate_image_urls(self, value):
        expected_base_url = StorageService.get_expected_response_base_url()
        expected_folder = f"/{UploadIntent.HAZARD_REPORTS.value}/"

        for url in value:
            if not url.startswith(expected_base_url) or expected_folder not in url:
                raise serializers.ValidationError("Invalid URL")

        return value


class GetReportListRequestSerializer(serializers.Serializer):
    #base
    q = serializers.CharField(required=False)
    category_id = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)

    #non-staff only
    created_at = serializers.DateField(required=False)

    #staff only
    exclude_closed = serializers.BooleanField(required=False, default=False)
    severity = serializers.CharField(required=False, min_length=2, max_length=2)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

    def validate(self, attrs):
        user = self.context.get("user")

        if user and user.is_staff:
            attrs.pop("created_at", None)
        else:
            attrs.pop("exclude_closed", None)
            attrs.pop("severity", None)
            attrs.pop("from_date", None)
            attrs.pop("to_date", None)

        return attrs


class UpdateReportRequestSerializer(serializers.Serializer):
    severity = serializers.CharField()
    status = serializers.CharField()
    remarks = serializers.CharField()
    resolution_image_urls = serializers.ListField(
        child=serializers.URLField(max_length=500),
        min_length=1,
        max_length=settings.STORAGE_CONFIG['MAX_SIGNATURE_COUNT']
    )

    def validate_resolution_image_urls(self, value):
        expected_base_url = StorageService.get_expected_response_base_url()
        expected_folder = f"/{UploadIntent.REPORT_RESOLUTION.value}/"

        for url in value:
            if not url.startswith(expected_base_url) or expected_folder not in url:
                raise serializers.ValidationError("Invalid URL")

        return value