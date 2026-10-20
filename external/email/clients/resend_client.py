import resend
from django.conf import settings

from .base_client import BaseEmailClient


class ResendClient(BaseEmailClient):
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY

    def deliver(
            self,
            *,
            from_email: str,
            to_emails: list[str],
            subject: str,
            html_body: str,
            text_body: str,
    ) -> bool:
        try:
            params: resend.Emails.SendParams = {
                "from": from_email,
                "to": to_emails,
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }

            resend.Emails.send(params)
            return True
        except Exception as e:
            return False
