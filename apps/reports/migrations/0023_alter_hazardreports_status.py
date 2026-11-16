from django.db import migrations, models


LEGACY_TO_NEW_STATUS = {
    'UNDER_REVIEW': 'IN_PROGRESS',
    'DISPATCHED': 'IN_PROGRESS',
    'ONGOING': 'IN_PROGRESS',
}

# Rollback is necessarily lossy: the three retired handling statuses collapse
# into In Progress, so reverse maps every In Progress row to Under Review.
NEW_TO_LEGACY_STATUS = {
    'IN_PROGRESS': 'UNDER_REVIEW',
}


def collapse_legacy_statuses(apps, schema_editor):
    HazardReports = apps.get_model('apps_reports', 'HazardReports')
    for legacy, new in LEGACY_TO_NEW_STATUS.items():
        HazardReports.objects.filter(status=legacy).update(status=new)


def restore_legacy_statuses(apps, schema_editor):
    HazardReports = apps.get_model('apps_reports', 'HazardReports')
    for new, legacy in NEW_TO_LEGACY_STATUS.items():
        HazardReports.objects.filter(status=new).update(status=legacy)


class Migration(migrations.Migration):

    dependencies = [
        ('apps_reports', '0022_remove_ai_flag_review_fields'),
    ]

    operations = [
        migrations.RunPython(collapse_legacy_statuses, restore_legacy_statuses),
        migrations.AlterField(
            model_name='hazardreports',
            name='status',
            field=models.CharField(
                choices=[
                    ('NEW', 'New'),
                    ('ASSIGNED', 'Assigned'),
                    ('IN_PROGRESS', 'In Progress'),
                    ('ON_HOLD', 'On-Hold'),
                    ('RESOLVED', 'Resolved'),
                    ('CLOSED', 'Closed'),
                    ('INVALID', 'Invalid'),
                ],
                db_index=True,
                default='NEW',
                max_length=20,
            ),
        ),
    ]
