import pytest

from external.ai import AIService, ImageFlagReason


def _noul(probability: float, confidence: float | None = None) -> dict:
    return {
        "type": "noul",
        "noul": probability,
        "confidence": (
            max(probability, 1 - probability)
            if confidence is None
            else confidence
        ),
    }


def _image_answers(
        index: int,
        *,
        ai_generated: float = 0.1,
        prank: float = 0.1,
        context: float = 0.9,
        ai_generated_confidence: float | None = None,
        prank_confidence: float | None = None,
        context_confidence: float | None = None,
) -> dict:
    return {
        f"image_{index}_ai_generated": _noul(
            ai_generated, ai_generated_confidence
        ),
        f"image_{index}_prank": _noul(prank, prank_confidence),
        f"image_{index}_context": _noul(context, context_confidence),
    }


def _mock_evaluate(monkeypatch, answers: dict) -> None:
    monkeypatch.setattr(
        AIService._client,
        "evaluate",
        lambda **_: answers,
    )


class TestMimeTypeInference:
    def test_infers_from_the_url_path_extension(self):
        assert AIService._infer_mime_type(
            "https://cdn.example.com/folder/photo.jpg"
        ) == "image/jpeg"
        assert AIService._infer_mime_type(
            "https://cdn.example.com/folder/photo.webp"
        ) == "image/webp"

    def test_falls_back_to_jpeg_without_an_extension(self):
        assert AIService._infer_mime_type(
            "https://cdn.example.com/folder/photo"
        ) == "image/jpeg"


class TestValidateReportImages:
    def test_sends_every_image_url_and_all_checks(self, monkeypatch):
        captured = {}

        def evaluate(**kwargs):
            captured.update(kwargs)
            return {
                **_image_answers(1),
                **_image_answers(2),
            }

        monkeypatch.setattr(AIService._client, "evaluate", evaluate)

        image_urls = [
            "https://res.cloudinary.com/demo/image/upload/one.jpg",
            "https://res.cloudinary.com/demo/image/upload/two.png",
        ]

        result = AIService.validate_report_images(
            image_urls=image_urls,
            category="Pothole",
            description="Large pothole on the road.",
        )

        image_parts = [
            part for part in captured["input_contents"] if part["type"] == "image"
        ]
        assert [part["uri"] for part in image_parts] == image_urls
        assert [part["mime_type"] for part in image_parts] == [
            "image/jpeg",
            "image/png",
        ]
        assert all(part["resolution"] == "medium" for part in image_parts)
        assert set(captured["questions"]) == {
            "image_1_ai_generated",
            "image_1_prank",
            "image_1_context",
            "image_2_ai_generated",
            "image_2_prank",
            "image_2_context",
        }
        assert result["success"] is True
        assert result["is_flagged"] is False
        assert result["flagged_reasons"] == []

    def test_flags_ai_generated_image(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            _image_answers(1, ai_generated=0.9),
        )

        result = AIService.validate_report_images(
            image_urls=["https://res.cloudinary.com/demo/image/upload/photo.jpg"],
            category="Pothole",
            description="Large pothole on the road.",
        )

        image = result["images"][0]
        assert result["is_flagged"] is True
        assert result["flagged_reasons"] == [ImageFlagReason.AI_GENERATED.value]
        assert image["is_ai_generated"] is True
        assert image["is_prank"] is False
        assert image["matches_context"] is True
        assert image["is_flagged"] is True
        assert image["flag_reasons"] == [ImageFlagReason.AI_GENERATED.value]
        assert "Possible AI-generated or synthetic image." in image["issues"]

    def test_flags_prank_image(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            _image_answers(1, prank=0.9),
        )

        result = AIService.validate_report_images(
            image_urls=["https://res.cloudinary.com/demo/image/upload/photo.jpg"],
            category="Pothole",
            description="Large pothole on the road.",
        )

        image = result["images"][0]
        assert result["is_flagged"] is True
        assert result["flagged_reasons"] == [ImageFlagReason.PRANK_OR_MEME.value]
        assert image["is_prank"] is True
        assert image["flag_reasons"] == [ImageFlagReason.PRANK_OR_MEME.value]
        assert (
            "Possible prank, meme, screenshot, or non-evidence image."
            in image["issues"]
        )

    def test_flags_image_that_does_not_match_the_report(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            _image_answers(1, context=0.1),
        )

        result = AIService.validate_report_images(
            image_urls=["https://res.cloudinary.com/demo/image/upload/photo.jpg"],
            category="Pothole",
            description="Large pothole on the road.",
        )

        image = result["images"][0]
        assert result["is_flagged"] is True
        assert result["flagged_reasons"] == [
            ImageFlagReason.CONTEXT_MISMATCH.value
        ]
        assert image["matches_context"] is False
        assert image["flag_reasons"] == [
            ImageFlagReason.CONTEXT_MISMATCH.value
        ]
        assert (
            "Image does not appear to match the report's category or description."
            in image["issues"]
        )

    def test_flags_low_confidence_result_for_manual_review(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            _image_answers(1, ai_generated_confidence=0.55),
        )

        result = AIService.validate_report_images(
            image_urls=["https://res.cloudinary.com/demo/image/upload/photo.jpg"],
            category="Pothole",
            description="Large pothole on the road.",
        )

        image = result["images"][0]
        assert result["is_flagged"] is True
        assert result["flagged_reasons"] == [
            ImageFlagReason.LOW_CONFIDENCE.value
        ]
        assert image["is_ai_generated"] is False
        assert image["is_prank"] is False
        assert image["matches_context"] is True
        assert image["flag_reasons"] == [
            ImageFlagReason.LOW_CONFIDENCE.value
        ]
        assert (
            "AI confidence is below the review threshold; manual review is required."
            in image["issues"]
        )

    def test_one_flagged_image_flags_the_entire_report(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            {
                **_image_answers(1),
                **_image_answers(2, context=0.1),
            },
        )

        image_urls = [
            "https://res.cloudinary.com/demo/image/upload/clean.jpg",
            "https://res.cloudinary.com/demo/image/upload/mismatch.jpg",
        ]

        result = AIService.validate_report_images(
            image_urls=image_urls,
            category="Pothole",
            description="Large pothole on the road.",
        )

        assert result["is_flagged"] is True
        assert result["flagged_image_urls"] == [image_urls[1]]
        assert result["flagged_reasons"] == [
            ImageFlagReason.CONTEXT_MISMATCH.value
        ]
        assert result["images"][0]["is_flagged"] is False
        assert result["images"][1]["is_flagged"] is True

    def test_deduplicates_report_level_reasons(self, monkeypatch):
        _mock_evaluate(
            monkeypatch,
            {
                **_image_answers(1, context=0.1),
                **_image_answers(2, context=0.1),
            },
        )

        result = AIService.validate_report_images(
            image_urls=[
                "https://res.cloudinary.com/demo/image/upload/one.jpg",
                "https://res.cloudinary.com/demo/image/upload/two.jpg",
            ],
            category="Pothole",
            description="Large pothole on the road.",
        )

        assert result["flagged_reasons"] == [
            ImageFlagReason.CONTEXT_MISMATCH.value
        ]

    def test_returns_unknown_flag_state_when_the_ai_call_fails(self, monkeypatch):
        def evaluate(**kwargs):
            raise RuntimeError("decision service unavailable")

        monkeypatch.setattr(AIService._client, "evaluate", evaluate)

        result = AIService.validate_report_images(
            image_urls=["https://res.cloudinary.com/demo/image/upload/photo.jpg"],
            category="Pothole",
        )

        assert result["success"] is False
        assert result["is_flagged"] is None
        assert result["images"] == []
        assert "decision service unavailable" in result["error"]

    def test_empty_image_list_skips_the_ai_call(self, monkeypatch):
        def evaluate(**kwargs):
            pytest.fail("AI should not be called without images")

        monkeypatch.setattr(AIService._client, "evaluate", evaluate)

        result = AIService.validate_report_images(
            image_urls=[],
            category="Pothole",
        )

        assert result["success"] is True
        assert result["is_flagged"] is False
        assert result["flagged_reasons"] == []
        assert result["images"] == []
