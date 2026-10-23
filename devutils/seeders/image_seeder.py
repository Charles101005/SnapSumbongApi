import random
from datetime import timedelta

from apps.reports.models import ReportImages
from devutils.factories import ReportImageFactory
from devutils.factories.base_factory import SeedData, chance, pick
from devutils.seeders.base_seeder import Progress, backdate
from devutils.seeders.report_seeder import ReportSeedInfo


def run(*, progress: Progress, infos: list[ReportSeedInfo]) -> dict:
    """Attach BEFORE / DURING / AFTER photos per DO 47 photolog rules.

    - Every report gets 1-2 BEFORE photos (the submission photos). Reports
      whose submission was flagged invalid use AFTER urls as the submitted
      photo, per the invalid-photo seeding trick.
    - Reports that reached RESOLVED also get DURING + AFTER photos, uploaded
      between the submission and the resolution.
    """
    urls = SeedData.image_urls()
    created = {"BEFORE": 0, "DURING": 0, "AFTER": 0}

    for info in infos:
        report = info.report

        # Submission photos.
        before_pool = urls["after"] if info.invalid_submission else urls["before"]
        before_count = 2 if chance(0.35) else 1
        for _ in range(before_count):
            image = ReportImageFactory(
                report=report,
                image_url=pick(before_pool),
                photo_type=ReportImages.PhotoType.BEFORE,
            )
            uploaded = info.created_at + timedelta(minutes=random.randint(1, 30))
            backdate(image, min(uploaded, _now()), ["uploaded_at"])
            created["BEFORE"] += 1

        # Photolog for resolved (and confirmed-closed) reports.
        if info.needs_resolution_images:
            works_start = info.created_at + timedelta(days=random.randint(1, 5))
            works_end = info.resolved_at - timedelta(hours=random.randint(1, 12))
            works_start = min(works_start, works_end)

            during = ReportImageFactory(
                report=report,
                image_url=pick(urls["during"]),
                photo_type=ReportImages.PhotoType.DURING,
            )
            during_at = works_start + (works_end - works_start) / 2
            backdate(during, min(during_at, _now()), ["uploaded_at"])
            created["DURING"] += 1

            after = ReportImageFactory(
                report=report,
                image_url=pick(urls["after"]),
                photo_type=ReportImages.PhotoType.AFTER,
            )
            backdate(after, min(works_end, _now()), ["uploaded_at"])
            created["AFTER"] += 1

    progress.done(
        f"{created['BEFORE']} before, {created['DURING']} during, "
        f"{created['AFTER']} after photos"
    )
    return created


def _now():
    from django.utils import timezone
    return timezone.now()
