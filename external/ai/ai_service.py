from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .clients import GoogleAIClient
from .constants import ImageFlagReason


class AIService:
    _client = GoogleAIClient()
    _decision_threshold = 0.55
    _confidence_threshold = 0.60

    _extension_mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }

    _flag_messages = {
        ImageFlagReason.AI_GENERATED: (
            "Possible AI-generated or synthetic image."
        ),
        ImageFlagReason.PRANK_OR_MEME: (
            "Possible prank, meme, screenshot, or non-evidence image."
        ),
        ImageFlagReason.CONTEXT_MISMATCH: (
            "Image does not appear to match the report's category or description."
        ),
        ImageFlagReason.LOW_CONFIDENCE: (
            "AI confidence is below the review threshold; manual review is "
            "required."
        ),
    }

    @classmethod
    def _infer_mime_type(cls, image_url: str) -> str:
        extension = PurePosixPath(urlparse(image_url).path).suffix.lower()
        return cls._extension_mime_types.get(extension, "image/jpeg")

    @classmethod
    def _build_input_contents(
            cls,
            *,
            image_urls: list[str],
            category: str,
            description: str
    ) -> list[dict[str, Any]]:
        context_text = (
            "You are screening images attached to a citizen-submitted public hazard report.\n"
            f"Report category: {category or 'Unspecified'}\n"
            f"Report description: {description or 'No description provided.'}\n"
            f"{len(image_urls)} image(s) follow in submission order: image 1 is "
            "the first image after this text, image 2 is the second, and so on."
        )

        contents: list[dict[str, Any]] = [{
            "type": "text",
            "text": context_text,
        }]

        for image_url in image_urls:
            contents.append({
                "type": "image",
                "uri": image_url,
                "mime_type": cls._infer_mime_type(image_url),
                "resolution": "medium",
            })

        return contents

    @classmethod
    def _build_questions(
            cls,
            *,
            image_urls: list[str],
            category: str,
            description: str
    ) -> dict[str, dict[str, Any]]:
        questions: dict[str, dict[str, Any]] = {}
        image_count = len(image_urls)

        for index in range(1, image_count + 1):
            # If AI-Generated or not
            questions[f"image_{index}_ai_generated"] = {
                "type": "noul",
                "instructions": (
                    f"Evaluate only image {index} (image {index} of {image_count}). "
                    "Return true only if the image appears AI-generated or "
                    "synthetic (for example generated, heavily edited, or rendered "
                    "imagery). Return false if it looks like an authentic, "
                    "unedited, real-world photograph taken by a camera."
                ),
                "criteria": {
                    "true_description": "AI-generated or synthetic imagery.",
                    "false_description": "Authentic real-world camera photograph.",
                },
            }

            # If fake or obviously invalid photo or not
            questions[f"image_{index}_prank"] = {
                "type": "noul",
                "instructions": (
                    f"Evaluate only image {index} (image {index} of {image_count}). "
                    "Return true only if the image is a prank or joke submission: "
                    "a meme, screenshot, stock or graphic illustration, or other "
                    "picture that is not genuine photographic evidence of a real "
                    "hazard. Return false for a genuine camera photograph."
                ),
                "criteria": {
                    "true_description": "Prank, meme, screenshot, or non-evidence image.",
                    "false_description": "Genuine camera photograph of a real scene.",
                },
            }

            # If there is mismatch between image and report context or not
            questions[f"image_{index}_context"] = {
                "type": "noul",
                "instructions": (
                    f"Evaluate only image {index} (image {index} of {image_count}) "
                    "against the report. Return true only if the image visibly "
                    "depicts the reported hazard or a scene consistent with it. "
                    f"Report category: {category or 'Unspecified'}. "
                    f"Report description: {description or 'No description provided.'} "
                    "Return false if the image is unrelated, shows a different "
                    "subject, or does not plausibly support the report."
                ),
                "criteria": {
                    "true_description": "Image clearly supports the reported category and description.",
                    "false_description": (
                        "Image is unrelated or inconsistent with the reported category and description."
                    ),
                },
            }

        return questions

    @classmethod
    def _get_probability(cls, answer: dict[str, Any] | None) -> float:
        if not answer:
            return 0.0
        return float(answer.get("noul", 0.0))

    @classmethod
    def _get_confidence(cls, answer: dict[str, Any] | None, probability: float) -> float:
        if answer and answer.get("confidence") is not None:
            return float(answer["confidence"])
        return max(probability, 1 - probability)

    @classmethod
    def validate_report_images(
            cls,
            *,
            image_urls: list[str],
            category: str,
            description: str = ""
    ) -> dict[str, Any]:
        if not image_urls:
            return {
                "success": True,
                "is_flagged": False,
                "flagged_reasons": [],
                "images": [],
                "flagged_image_urls": [],
                "category": category,
                "description": description,
                "error": None,
            }

        try:
            answers = cls._client.evaluate(
                input_contents=cls._build_input_contents(
                    image_urls=image_urls,
                    category=category,
                    description=description,
                ),
                questions=cls._build_questions(
                    image_urls=image_urls,
                    category=category,
                    description=description,
                ),
            )
        except Exception as error:
            return {
                "success": False,
                "is_flagged": None,
                "flagged_reasons": [],
                "images": [],
                "flagged_image_urls": [],
                "category": category,
                "description": description,
                "error": str(error),
            }

        screened_images: list[dict[str, Any]] = []
        flagged_image_urls: list[str] = []
        report_flag_reasons: list[str] = []

        for index, image_url in enumerate(image_urls, start=1):
            ai_generated_answer = answers.get(f"image_{index}_ai_generated")
            prank_answer = answers.get(f"image_{index}_prank")
            context_answer = answers.get(f"image_{index}_context")

            ai_generated_probability = cls._get_probability(ai_generated_answer)
            prank_probability = cls._get_probability(prank_answer)
            context_probability = cls._get_probability(context_answer)

            ai_generated_confidence = cls._get_confidence(ai_generated_answer, ai_generated_probability)
            prank_confidence = cls._get_confidence(prank_answer, prank_probability)
            context_confidence = cls._get_confidence(context_answer, context_probability)

            is_ai_generated = ai_generated_probability >= cls._decision_threshold
            is_prank = prank_probability >= cls._decision_threshold
            matches_context = context_probability >= cls._decision_threshold
            meets_confidence_threshold = (
                ai_generated_confidence >= cls._confidence_threshold
                and prank_confidence >= cls._confidence_threshold
                and context_confidence >= cls._confidence_threshold
            )

            flag_reasons: list[ImageFlagReason] = []
            if is_ai_generated:
                flag_reasons.append(ImageFlagReason.AI_GENERATED)
            if is_prank:
                flag_reasons.append(ImageFlagReason.PRANK_OR_MEME)
            if not matches_context:
                flag_reasons.append(ImageFlagReason.CONTEXT_MISMATCH)
            if not meets_confidence_threshold:
                flag_reasons.append(ImageFlagReason.LOW_CONFIDENCE)

            is_flagged = bool(flag_reasons)

            if is_flagged:
                flagged_image_urls.append(image_url)

                for reason in flag_reasons:
                    if reason.value not in report_flag_reasons:
                        report_flag_reasons.append(reason.value)

            screened_images.append({
                "image_url": image_url,
                "mime_type": cls._infer_mime_type(image_url),
                "is_ai_generated": is_ai_generated,
                "ai_generated_probability": round(ai_generated_probability, 4),
                "ai_generated_confidence": round(ai_generated_confidence, 4),
                "is_prank": is_prank,
                "prank_probability": round(prank_probability, 4),
                "prank_confidence": round(prank_confidence, 4),
                "matches_context": matches_context,
                "context_probability": round(context_probability, 4),
                "context_confidence": round(context_confidence, 4),
                "is_flagged": is_flagged,
                "flag_reasons": [reason.value for reason in flag_reasons],
                "issues": [cls._flag_messages[reason] for reason in flag_reasons],
            })

        return {
            "success": True,
            "is_flagged": bool(flagged_image_urls),
            "flagged_reasons": report_flag_reasons,
            "images": screened_images,
            "flagged_image_urls": flagged_image_urls,
            "category": category,
            "description": description,
            "error": None,
        }
