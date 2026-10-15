from typing import Any

from django.db import transaction

from apps.accounts.models import Users, CitizenWarnings
from apps.accounts.domain_errors.user_error import (
    UserNotFoundError,
    WarnTargetInactiveError,
    LinkedReportNotInvalidError,
    LinkedReportNotOwnedError,
    BanTargetInactiveError,
    BanSelfDeniedError,
    BanNotEligibleError,
    FastTrackReportNotInvalidError,
    FastTrackReportNotOwnedError,
    UnbanTargetNotInactiveError,
)
from apps.audits.services import AuditLogService
from apps.reports.models import HazardReports
from shared.results import DomainResult


BAN_WARNING_THRESHOLD = 3


class ModerationService:
    @staticmethod
    def _find_citizen(user_number: str) -> Users|None:
        return Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=False,
        ).select_related("role").first()

    @staticmethod
    @transaction.atomic
    def issue_warning(
            *,
            actor: Users,
            user_number: str,
            reason: str,
            report_number: str|None=None,
    ) -> DomainResult[CitizenWarnings]:
        citizen = ModerationService._find_citizen(user_number)
        if citizen is None:
            return DomainResult.error(UserNotFoundError)

        if not citizen.is_active:
            return DomainResult.error(WarnTargetInactiveError)

        report = None
        if report_number:
            report = HazardReports.objects.filter(
                report_number__iexact=report_number
            ).first()

            if report is None:
                return DomainResult.error(UserNotFoundError)

            if report.status != HazardReports.Status.INVALID:
                return DomainResult.error(LinkedReportNotInvalidError)

            if report.reported_by_id != citizen.user_id:
                return DomainResult.error(LinkedReportNotOwnedError)

        warning = CitizenWarnings.objects.create(
            user=citizen,
            warned_by=actor,
            reason=reason,
            report=report,
        )

        AuditLogService.log_warning(
            user=actor,
            warned_user=citizen,
            reason=reason,
            warning_number=warning.warning_number,
            report_number=report_number,
        )

        return DomainResult.success(warning)

    @staticmethod
    @transaction.atomic
    def ban_citizen(
            *,
            actor: Users,
            user_number: str,
            reason: str,
            report_number: str|None=None,
    ) -> DomainResult[None]:
        citizen = ModerationService._find_citizen(user_number)
        if citizen is None:
            return DomainResult.error(UserNotFoundError)

        if actor.user_id == citizen.user_id:
            return DomainResult.error(BanSelfDeniedError)

        if not citizen.is_active:
            return DomainResult.error(BanTargetInactiveError)

        warning_count = CitizenWarnings.objects.filter(user=citizen).count()

        if warning_count >= BAN_WARNING_THRESHOLD:
            pass  # Count path: eligible.
        elif report_number:
            report = HazardReports.objects.filter(
                report_number__iexact=report_number
            ).first()

            if report is None:
                return DomainResult.error(BanNotEligibleError)

            if report.status != HazardReports.Status.INVALID:
                return DomainResult.error(FastTrackReportNotInvalidError)

            if report.reported_by_id != citizen.user_id:
                return DomainResult.error(FastTrackReportNotOwnedError)
        else:
            return DomainResult.error(BanNotEligibleError)

        citizen.is_active = False
        citizen.save(update_fields=["is_active"])

        AuditLogService.log_ban(
            user=actor,
            banned_user=citizen,
            reason=reason,
            fast_track_report_number=report_number if warning_count < BAN_WARNING_THRESHOLD else None,
        )

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def unban_citizen(
            *,
            actor: Users,
            user_number: str,
            reason: str,
    ) -> DomainResult[None]:
        citizen = ModerationService._find_citizen(user_number)
        if citizen is None:
            return DomainResult.error(UserNotFoundError)

        if citizen.is_active:
            return DomainResult.error(UnbanTargetNotInactiveError)

        citizen.is_active = True
        citizen.save(update_fields=["is_active"])

        AuditLogService.log_unban(
            user=actor,
            unbanned_user=citizen,
            reason=reason,
        )

        return DomainResult.success(None)

    @staticmethod
    def get_citizen_warnings(
            *,
            user: Users,
    ) -> DomainResult[dict[str, Any]]:
        warnings = CitizenWarnings.objects.filter(
            user=user
        ).select_related(
            "warned_by",
            "report",
        ).order_by("-created_at")

        warning_list = [
            {
                "warning_number": w.warning_number,
                "reason": w.reason,
                "report_number": w.report.report_number if w.report else None,
                "warned_by_name": w.warned_by.get_full_name() if w.warned_by else None,
                "created_at": w.created_at,
            }
            for w in warnings
        ]

        return DomainResult.success({
            "count": len(warning_list),
            "warnings": warning_list,
        })

    @staticmethod
    def get_moderation_summary(
            *,
            user: Users,
    ) -> DomainResult[dict[str, Any]]:
        warning_count = CitizenWarnings.objects.filter(user=user).count()

        return DomainResult.success({
            "warning_count": warning_count,
            "is_active": user.is_active,
        })

    @staticmethod
    def get_warnings_for_user(
            *,
            user_number: str,
    ) -> DomainResult[dict[str, Any]]:
        citizen = ModerationService._find_citizen(user_number)
        if citizen is None:
            return DomainResult.error(UserNotFoundError)

        return ModerationService.get_citizen_warnings(user=citizen)
