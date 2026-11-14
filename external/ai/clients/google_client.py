from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

from .base_client import BaseAIClient


class GoogleAIClient(BaseAIClient):
    _api_key = settings.GOOGLE_AI_API_KEY
    _model = "gemini-decision-1"
    _api_version = "v1beta"
    _timeout_seconds = 45

    def __init__(self):
        self.client: genai.Client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                api_version=self._api_version,
                timeout=self._timeout_seconds * 1000,
            )
        )

    def evaluate(
            self,
            *,
            input_contents: list[dict[str, Any]],
            questions: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        response = self.client.decisions.create(
            model=self._model,
            input=input_contents,
            questions=questions,
        )

        answers = response.answers or {}
        return {
            question_id: (
                answer.model_dump()
                if hasattr(answer, "model_dump")
                else dict(answer)
            )
            for question_id, answer in answers.items()
        }
