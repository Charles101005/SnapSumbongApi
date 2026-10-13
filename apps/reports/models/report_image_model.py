from django.db import models

from .hazard_report_model import HazardReports


class ReportImages(models.Model):
    # DO 47 s.2024 Appendix A-8: Documentation Photolog shows the rectification
    # activity as Before (hazard as reported), During (works in progress), and
    # After (completed rectification) photographs.
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
