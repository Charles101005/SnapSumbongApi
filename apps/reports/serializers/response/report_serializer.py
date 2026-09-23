from typing import Any
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from rest_framework import serializers

from apps.reports.models import HazardReports
from apps.audits.models import AuditLogs


class _ImageSignatureSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    signature = serializers.CharField()


class ReportImageSignatureResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    upload_url = serializers.URLField()
    upload_preset = serializers.CharField()
    asset_folder = serializers.CharField()
    use_asset_folder_as_public_id_prefix = serializers.BooleanField()
    timestamp = serializers.IntegerField()
    image_signatures = _ImageSignatureSerializer(many=True)


class CreateReportResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    reported_by = serializers.CharField()
    created_at = serializers.DateTimeField()


class GetReportListResponseSerializer(serializers.Serializer):
    #base/non-staff
    report_number = serializers.CharField(min_length=20, max_length=20)
    category = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    #staff only
    severity = serializers.CharField(min_length=2, max_length=2)
    address = serializers.CharField(max_length=225)

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("user")

        if not user or not user.is_staff:
            data.pop("severity", None)
            data.pop("address", None)

        return data


class GetReportDetailResponseSerializer(serializers.Serializer):
    #base
    report_number = serializers.CharField(min_length=20, max_length=20)
    status = serializers.SerializerMethodField()

    latitude = serializers.DecimalField(
        max_digits=8,
        decimal_places=6,
        min_value=Decimal('-90.0'),
        max_value=Decimal('90.0')
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal('-180.0'),
        max_value=Decimal('180.0')
    )

    address = serializers.CharField(max_length=255)
    description = serializers.CharField()
    remarks = serializers.CharField()

    image_urls = serializers.SerializerMethodField()

    #non-staff only
    status_timeline = serializers.SerializerMethodField()
    next_expected_statuses = serializers.ListField(child=serializers.CharField())
    resolution_image_urls = serializers.SerializerMethodField()

    #staff only
    reported_by = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    severity = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def get_reported_by(self, value) -> str:
        if not value.is_anonymous:
            reported_by = value.reported_by

            middle_name = f" {reported_by.middle_name[0].upper()}." if reported_by.middle_name else ""
            full_name = f"{reported_by.last_name}, {reported_by.first_name}{middle_name}"

            return full_name

        return "<Anonymous>"

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_image_urls(self, value) -> list:
        return [image.image_url for image in value.images.all() if image.is_resolution is False]

    def get_resolution_image_urls(self, value) -> list:
        return [image.image_url for image in value.images.all() if image.is_resolution is True]

    def get_status_timeline(self, value) -> list:
        audit_logs = [
            audit_log
            for audit_log in value.audit_logs.all()
            if audit_log.action in (AuditLogs.ActionType.CREATE, AuditLogs.ActionType.STATUS_CHANGE)
        ]
        status_timeline = []

        for audit_log in audit_logs:
            payload = audit_log.payload
            status = payload["initial_status"] if payload.get("initial_status") else payload["status_change"]["to"]

            status_timeline.append({
                "status": status,
                "created_at": audit_log.created_at.isoformat(),
            })
        return status_timeline

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("user")

        if user and user.is_staff:
            data.pop("status_timeline", None)
            data.pop("next_expected_statuses", None)
            data.pop("resolution_image_urls", None)

        else:
            data.pop("reported_by", None)
            data.pop("category", None)
            data.pop("severity", None)
            data.pop("created_at", None)

        return data


class GetReportHistoryDetailResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    address = serializers.CharField(max_length=225)
    severity = serializers.CharField()
    description = serializers.CharField()

    status = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    image_urls = serializers.SerializerMethodField()
    resolution_image_urls = serializers.SerializerMethodField()

    status_timeline = serializers.SerializerMethodField()

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_image_urls(self, value) -> list[str]:
        return [image.image_url for image in value.images.all() if image.is_resolution is False]

    def get_resolution_image_urls(self, value) -> list[str]:
        return [image.image_url for image in value.images.all() if image.is_resolution is True]

    def get_status_timeline(self, value) -> list[dict[str, Any]]:
        audit_logs = [
            audit_log
            for audit_log in value.audit_logs.all()
            if audit_log.action in (AuditLogs.ActionType.CREATE, AuditLogs.ActionType.STATUS_CHANGE)
        ]
        status_timeline = []

        for audit_log in audit_logs:
            payload = audit_log.payload
            status = payload["initial_status"] if payload.get("initial_status") else payload["status_change"]["to"]

            user = audit_log.user
            if user:
                if not user.is_staff and value.is_anonymous:
                    name = "<Anonymous>"

                else:
                    middle_name = f" {user.middle_name[0].upper()}." if user.middle_name else ""
                    name = f"{user.last_name}, {user.first_name}{middle_name}"

            else:
                name = "System"


            status_log_detail = {
                "audit_log_number": audit_log.audit_log_number,
                "module": f"{AuditLogs.ModuleType(audit_log.module).label} Management",
                "action": AuditLogs.ActionType(audit_log.action).label,
                "description": audit_log.description,
                "status": status,
                "created_at": audit_log.created_at.isoformat(),
                "performed_by": {
                    "name": name,
                    "role": user.role.role_name if user else None
                }
            }

            status_timeline.append(status_log_detail)

        return status_timeline