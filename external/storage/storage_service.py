from typing import Any
from django.conf import settings

from .clients import CloudinaryClient
from .constants import UploadIntent


class StorageService:
    _client = CloudinaryClient()

    _expires_in = settings.STORAGE_CONFIG["EXPIRES_IN"]

    @classmethod
    def get_upload_credentials(
            cls,
            *,
            folder_path: str,
            file_names: list[str],
            intent: UploadIntent
    ) -> dict[str, Any]:
        return cls._client.generate_signature(
            folder_path=folder_path,
            file_names=file_names,
            intent=intent,
            expires_in=cls._expires_in,
        )

    @classmethod
    def get_expected_response_base_url(cls):
        return cls._client.get_expected_response_base_url()