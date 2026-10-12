import re
from typing import Any

from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .clients import ResendClient


class EmailService:
    _client = ResendClient()

    @classmethod
    def _compile_and_send(
            cls,
            *,
            to_emails: list[str],
            subject: str,
            template_path: str,
            context: dict[str, Any]
    ) -> bool:
        html_body = render_to_string(template_path, context)

        raw_text = strip_tags(html_body)
        text_body = re.sub(r"\n\s*\n", "\n\n", raw_text).strip()

        return cls._client.deliver(
            to_emails=to_emails,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

    @classmethod
    def send_registration_otp(
            cls,
            *,
            to_email: str,
            otp_code: str,
    ) -> bool:
        return cls._compile_and_send(
            to_emails=[to_email],
            subject="Activate Your Account",
            template_path="verification_otp.html",
            context={"otp_code": otp_code}
        )
