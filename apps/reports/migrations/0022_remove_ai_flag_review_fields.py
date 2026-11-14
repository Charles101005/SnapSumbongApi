from django.db import migrations


def clear_reviewed_ai_flags(apps, schema_editor):
    """Drop the flags on reports whose AI review already happened.

    0021 gave historical reports a review state. Under the new model there is
    no separate review state: a reviewed flag is simply cleared from the report
    and its images, and the history lives in the audit trail.
    """
    HazardReports = apps.get_model("apps_reports", "HazardReports")
    ReportImages = apps.get_model("apps_reports", "ReportImages")

    reviewed_report_ids = list(
        HazardReports.objects.filter(
            ai_flag_review_status__in=["CLEARED", "CONFIRMED"],
        ).values_list("report_id", flat=True)
    )

    if not reviewed_report_ids:
        return

    ReportImages.objects.filter(
        report_id__in=reviewed_report_ids,
        is_ai_flagged=True,
    ).update(is_ai_flagged=False)
    HazardReports.objects.filter(
        report_id__in=reviewed_report_ids,
        is_ai_flagged=True,
    ).update(is_ai_flagged=False)


class Migration(migrations.Migration):

    dependencies = [
        ('apps_reports', '0021_hazardreports_ai_flag_review'),
    ]

    operations = [
        migrations.RunPython(
            clear_reviewed_ai_flags,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='reportimages',
            name='ai_flag_reasons',
        ),
        migrations.RemoveField(
            model_name='hazardreports',
            name='ai_flag_review_status',
        ),
        migrations.RemoveField(
            model_name='hazardreports',
            name='ai_flag_reviewed_by',
        ),
        migrations.RemoveField(
            model_name='hazardreports',
            name='ai_flag_reviewed_at',
        ),
    ]
