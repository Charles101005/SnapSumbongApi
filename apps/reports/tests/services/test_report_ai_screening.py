from decimal import Decimal

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audits.models import AuditLogs
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardCategoryFactory
from external.ai import AIService, ImageFlagReason


IMAGE_ONE = "https://res.cloudinary.com/demo/image/upload/v123/hazard_reports/one.jpg"
IMAGE_TWO = "https://res.cloudinary.com/demo/image/upload/v456/hazard_reports/two.jpg"


def _screening_result(*, images: list[dict]) -> dict:
    flagged = [image for image in images if image["is_flagged"]]
    reasons: list[str] = []

    for image in flagged:
        for reason in image["flag_reasons"]:
            if reason not in reasons:
                reasons.append(reason)

    return {
        "success": True,
        "is_flagged": bool(flagged),
        "flagged_reasons": reasons,
        "flagged_image_urls": [image["image_url"] for image in flagged],
        "images": images,
        "category": "Pothole",
        "description": "Large pothole on the road.",
        "error": None,
    }


def _image_result(
        image_url: str,
        *,
        is_flagged: bool = False,
        flag_reasons: list[str] | None = None,
) -> dict:
    return {
        "image_url": image_url,
        "is_flagged": is_flagged,
        "flag_reasons": flag_reasons or [],
    }


def _create_report(*, citizen, image_urls: list[str]):
    return ReportService.create_assign_hazard_report(
        reported_by_id=citizen.user_id,
        category_id=HazardCategoryFactory().hazard_id,
        latitude=Decimal("14.599500"),
        longitude=Decimal("120.984200"),
        address="Sampaloc, Manila, Metro Manila",
        description="Large pothole on the road.",
        is_anonymous=False,
        image_urls=image_urls,
    ).value


@pytest.mark.django_db
class TestReportAiImageScreening:
    def test_one_flagged_image_flags_the_whole_report(
            self, monkeypatch, settings, citizen_role
    ):
        settings.AI_IMAGE_SCREENING_ENABLED = True
        monkeypatch.setattr(
            AIService,
            "validate_report_images",
            lambda **_: _screening_result(images=[
                _image_result(IMAGE_ONE),
                _image_result(
                    IMAGE_TWO,
                    is_flagged=True,
                    flag_reasons=[ImageFlagReason.CONTEXT_MISMATCH.value],
                ),
            ]),
        )

        report = _create_report(
            citizen=UserFactory(role=citizen_role),
            image_urls=[IMAGE_ONE, IMAGE_TWO],
        )

        report.refresh_from_db()
        assert report.is_ai_flagged is True
        assert report.ai_flag_reasons == [ImageFlagReason.CONTEXT_MISMATCH.value]

        images = list(report.images.order_by("report_image_id"))
        assert images[0].is_ai_flagged is False
        assert images[1].is_ai_flagged is True

        log = AuditLogs.objects.get(
            action=AuditLogs.ActionType.AI_FLAG_DETECTED,
            object_id=report.report_id,
        )
        assert log.user_id is None
        assert log.payload["ai_flag_detection"]["reasons"] == [
            ImageFlagReason.CONTEXT_MISMATCH.value
        ]
        assert log.payload["ai_flag_detection"]["flagged_images"] == [
            {"image_url": IMAGE_TWO}
        ]
        assert "flagged by automatic AI screening" in log.description

    def test_clean_report_is_not_flagged(
            self, monkeypatch, settings, citizen_role
    ):
        settings.AI_IMAGE_SCREENING_ENABLED = True
        monkeypatch.setattr(
            AIService,
            "validate_report_images",
            lambda **_: _screening_result(images=[
                _image_result(IMAGE_ONE),
                _image_result(IMAGE_TWO),
            ]),
        )

        report = _create_report(
            citizen=UserFactory(role=citizen_role),
            image_urls=[IMAGE_ONE, IMAGE_TWO],
        )

        report.refresh_from_db()
        assert report.is_ai_flagged is False
        assert report.ai_flag_reasons == []
        assert all(image.is_ai_flagged is False for image in report.images.all())
        assert not AuditLogs.objects.filter(
            action=AuditLogs.ActionType.AI_FLAG_DETECTED,
            object_id=report.report_id,
        ).exists()

    def test_failed_screening_fails_open(
            self, monkeypatch, settings, citizen_role
    ):
        settings.AI_IMAGE_SCREENING_ENABLED = True

        def evaluate(**_):
            raise RuntimeError("decision service unavailable")

        monkeypatch.setattr(AIService, "validate_report_images", evaluate)

        report = _create_report(
            citizen=UserFactory(role=citizen_role),
            image_urls=[IMAGE_ONE],
        )

        report.refresh_from_db()
        assert report.is_ai_flagged is False
        assert report.ai_flag_reasons == []
        assert report.images.get().is_ai_flagged is False
        assert not AuditLogs.objects.filter(
            action=AuditLogs.ActionType.AI_FLAG_DETECTED,
            object_id=report.report_id,
        ).exists()

    def test_screening_is_skipped_when_disabled(
            self, monkeypatch, settings, citizen_role
    ):
        settings.AI_IMAGE_SCREENING_ENABLED = False

        def evaluate(**_):
            pytest.fail("AI screening must not run when disabled")

        monkeypatch.setattr(AIService, "validate_report_images", evaluate)

        report = _create_report(
            citizen=UserFactory(role=citizen_role),
            image_urls=[IMAGE_ONE],
        )

        report.refresh_from_db()
        assert report.is_ai_flagged is False
        assert report.images.get().is_ai_flagged is False
        assert not AuditLogs.objects.filter(
            action=AuditLogs.ActionType.AI_FLAG_DETECTED,
            object_id=report.report_id,
        ).exists()
