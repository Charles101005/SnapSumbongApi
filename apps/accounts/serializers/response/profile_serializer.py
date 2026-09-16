from rest_framework import serializers


class GetProfileResponseSerializer(serializers.Serializer):
    last_name = serializers.CharField()
    first_name = serializers.CharField()
    middle_name = serializers.CharField(default=None)
    email = serializers.EmailField()
    contact_number = serializers.CharField(default=None)
    is_notified = serializers.BooleanField()
    profile_picture = serializers.URLField(default=None)


class GetProfileImageSignatureResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    upload_url = serializers.URLField()
    upload_preset = serializers.CharField()
    asset_folder = serializers.CharField()
    use_asset_folder_as_public_id_prefix = serializers.BooleanField()
    timestamp = serializers.IntegerField()

    public_id = serializers.SerializerMethodField()
    signature = serializers.SerializerMethodField()

    def get_public_id(self, obj):
        return obj["image_signatures"][0]["public_id"]

    def get_signature(self, obj):
        return obj["image_signatures"][0]["signature"]
