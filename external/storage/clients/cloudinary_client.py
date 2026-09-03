from typing import Any
from datetime import timedelta

from cloudinary.utils import api_sign_request
from django.conf import settings
from django.utils import timezone

from external.storage.constants import UploadIntent


class CloudinaryClient:
    def __init__(self):
        self._cloud_name = settings.CLOUDINARY_CLOUD_NAME
        self._api_key = settings.CLOUDINARY_API_KEY
        self._api_secret = settings.CLOUDINARY_API_SECRET

    def _get_upload_url(self) -> str:
        return f"https://api.cloudinary.com/v1_1/{self._cloud_name}/image/upload"

    def _map_intent_to_upload_preset(self, intent: UploadIntent) -> str:
        mapping = {
            UploadIntent.HAZARD_REPORT: "hazard_report_image",
            UploadIntent.USER_PROFILE: "user_profile_picture"
        }
        return mapping[intent]

    def get_expected_response_base_url(self) -> str:
        return f"https://res.cloudinary.com/{self._cloud_name}/image/upload/"

    def generate_signature(
            self,
            *,
            folder_path: str,
            file_names: list[str],
            intent: UploadIntent,
            expires_in: timedelta,
    ) -> dict[str, Any]:
        backdated_datetime = timezone.now() - (timedelta(hours=1) - expires_in)
        timestamp = int(backdated_datetime.timestamp())

        upload_preset = self._map_intent_to_upload_preset(intent)

        base_unsigned_params = {
            "asset_folder": folder_path,
            "use_asset_folder_as_public_id_prefix": True,
            "upload_preset": upload_preset,
            "timestamp": timestamp,
        }

        image_signatures = []
        for file_name in file_names:
            unsigned_params = {
                "public_id": file_name,
                **base_unsigned_params,
            }

            signature = api_sign_request(unsigned_params, self._api_secret, algorithm="sha256")

            image_signatures.append({
                "public_id": file_name,
                "signature": signature,
            })

        return {
            "upload_url": self._get_upload_url(),
            "api_key": self._api_key,
            "image_signatures": image_signatures,
            **base_unsigned_params
        }