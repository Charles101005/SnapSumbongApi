from django.db import models

from .hazard_report_model import HazardReports


class ReportImages(models.Model):
    report_image_id = models.BigAutoField(primary_key=True)

    image_url = models.URLField(max_length=500)
    report = models.ForeignKey(HazardReports, on_delete=models.CASCADE, related_name='images')
    is_resolution = models.BooleanField(default=False)

    uploaded_at = models.DateTimeField(auto_now_add=True)
