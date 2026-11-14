from abc import ABC, abstractmethod
from typing import Any


class BaseAIClient(ABC):
    @abstractmethod
    def evaluate(
            self,
            *,
            input_contents: list[dict[str, Any]],
            questions: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        pass
