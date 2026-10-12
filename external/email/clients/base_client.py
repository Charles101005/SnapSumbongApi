from abc import ABC, abstractmethod


class BaseEmailClient(ABC):
    @abstractmethod
    def deliver(
            self,
            *,
            to_emails: list[str],
            subject: str,
            html_body: str,
            text_body: str,
    ) -> bool:
        pass