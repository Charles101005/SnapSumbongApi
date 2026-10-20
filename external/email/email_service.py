import re
from typing import Any

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .clients import ResendClient


class EmailService:
    _client = ResendClient()
    _app_name = "SnapSumbong"

    # Dev-only switch: when DEBUG is True, controls whether an email is
    # actually handed to Resend (sent to the resend.dev domain) or only
    # printed to the console. Completely inert in prod (DEBUG=False) --
    # prod always sends and never prints.
    _dev_email_enabled: bool = True

    @classmethod
    def _resolve_sender(cls, *, auth: bool) -> str:
        if settings.DEBUG:
            return settings.DEFAULT_FROM_EMAIL  # SnapSumbong <onboarding@resend.dev>

        if auth:
            return settings.EMAIL_FROM_AUTH or settings.DEFAULT_FROM_EMAIL
        return settings.EMAIL_FROM_GENERAL or settings.DEFAULT_FROM_EMAIL

    @classmethod
    def _should_send(cls) -> bool:
        return cls._dev_email_enabled if settings.DEBUG else True

    @classmethod
    def _print_to_console(
            cls,
            *,
            from_email: str,
            to_emails: list[str],
            subject: str,
            text_body: str
    ) -> None:
        separator = "=" * 60
        to_line = ", ".join(to_emails)
        print(f"\n{separator}")
        print("[EmailService] EMAIL NOT SENT VIA RESEND (dev console)")
        print(separator)
        print(f"From:    {from_email}")
        print(f"To:      {to_line}")
        print(f"Subject: {subject}")
        print(separator)
        print(text_body)
        print(separator + "\n")

    @classmethod
    def _compile_and_send(
            cls,
            *,
            from_email: str,
            to_emails: list[str],
            subject: str,
            template_path: str,
            context: dict[str, Any]
    ) -> bool:
        html_body = render_to_string(template_path, context)

        # Drop <style> blocks first: strip_tags would otherwise leave the raw
        # CSS as visible text in the plain-text body.
        text_source = re.sub(r"<style\b.*?</style>", "", html_body, flags=re.IGNORECASE | re.DOTALL)
        raw_text = strip_tags(text_source)
        text_body = re.sub(r"\n\s*\n", "\n\n", raw_text).strip()

        if settings.DEBUG:
            cls._print_to_console(
                from_email=from_email,
                to_emails=to_emails,
                subject=subject,
                text_body=text_body
            )
            if not cls._should_send():
                # Dev, flag off: console-only, report success without sending.
                return True

        return cls._client.deliver(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

    @classmethod
    def _send_verification_otp(
            cls,
            *,
            verification_type: str,
            to_email: str,
            to_first_name: str,
            otp_code: str,
            expiry_minutes: str|int
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=True),
            to_emails=[to_email],
            subject=f"Your {cls._app_name} {verification_type.lower()} code",
            template_path="verification_otp.html",
            context={
                "verification_type": verification_type,
                "otp_code": otp_code,
                "expiry_minutes": expiry_minutes,
                "first_name": to_first_name,
                "app_name": cls._app_name,
            }
        )

    @classmethod
    def send_registration_otp(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            otp_code: str,
            expiry_minutes: str|int
    ) -> bool:
        return cls._send_verification_otp(
            verification_type="Registration",
            to_email=to_email,
            to_first_name=to_first_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes
        )

    @classmethod
    def send_password_reset_otp(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            otp_code: str,
            expiry_minutes: str|int
    ) -> bool:
        return cls._send_verification_otp(
            verification_type="Password Reset",
            to_email=to_email,
            to_first_name=to_first_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes
        )

    @classmethod
    def send_report_successful_submission(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            report_number: str,
            category: str,
            location: str,
            submitted_at: str
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=False),
            to_emails=[to_email],
            subject=f"We received your report {report_number}",
            template_path="report_successful_submission.html",
            context={
                "first_name": to_first_name,
                "report_number": report_number,
                "category": category,
                "location": location,
                "submitted_at": submitted_at,
            }
        )

    @classmethod
    def send_report_status_update(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            report_number: str,
            category: str,
            location: str,
            submitted_at: str,
            old_status: str,
            new_status: str,
            remarks: str = ""
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=False),
            to_emails=[to_email],
            subject=f"Your report {report_number} is now {new_status}",
            template_path="report_status_update.html",
            context={
                "first_name": to_first_name,
                "report_number": report_number,
                "category": category,
                "location": location,
                "submitted_at": submitted_at,
                "old_status": old_status,
                "new_status": new_status,
                "remarks": remarks,
            }
        )

    @classmethod
    def send_user_banned(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            case_id: str,
            flagged_report_count: int,
            total_report_count: int,
            reason: str,
            flagged_report_numbers: list[str]
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=False),
            to_emails=[to_email],
            subject=f"Your {cls._app_name} account has been banned",
            template_path="user_banned.html",
            context={
                "first_name": to_first_name,
                "email": to_email,
                "case_id": case_id,
                "flagged_report_count": flagged_report_count,
                "total_report_count": total_report_count,
                "reason": reason,
                "flagged_report_numbers": flagged_report_numbers,
                "app_name": cls._app_name,
            }
        )

    @classmethod
    def send_user_self_deactivation(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            full_name: str
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=False),
            to_emails=[to_email],
            subject=f"Your {cls._app_name} account has been deactivated",
            template_path="user_self_deactivation.html",
            context={
                "first_name": to_first_name,
                "email": to_email,
                "full_name": full_name,
                "app_name": cls._app_name,
            }
        )

    @classmethod
    def send_employee_creation_temporary_password(
            cls,
            *,
            to_email: str,
            to_first_name: str,
            user_number: str,
            assigned_role: str,
            temp_password: str
    ) -> bool:
        return cls._compile_and_send(
            from_email=cls._resolve_sender(auth=False),
            to_emails=[to_email],
            subject=f"Your {cls._app_name} staff account has been created",
            template_path="employee_creation_temporary_password.html",
            context={
                "first_name": to_first_name,
                "user_number": user_number,
                "assigned_role": assigned_role,
                "temp_password": temp_password,
                "app_name": cls._app_name,
            }
        )
