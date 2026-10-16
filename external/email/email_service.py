import re
from typing import Any

from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .clients import ResendClient


class EmailService:
    _client = ResendClient()
    _app_name = "SnapSumbong"

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
