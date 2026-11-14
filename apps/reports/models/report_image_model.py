from django.db import models

from .hazard_report_model import HazardReports


class ReportImages(models.Model):
    class PhotoType(models.TextChoices):
        BEFORE = 'BEFORE', 'Before'
        DURING = 'DURING', 'During'
        AFTER = 'AFTER', 'After'

    report_image_id = models.BigAutoField(primary_key=True)

    image_url = models.URLField(max_length=500)
    report = models.ForeignKey(HazardReports, on_delete=models.CASCADE, related_name='images')
    photo_type = models.CharField(
        max_length=10,
        choices=PhotoType.choices,
        default=PhotoType.BEFORE,
        db_index=True,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Per-image result of the preliminary AI screening. A flagged image always
    # means a human must review it; it is never an automatic rejection.
    is_ai_flagged = models.BooleanField(default=False, db_index=True)
