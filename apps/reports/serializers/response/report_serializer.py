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