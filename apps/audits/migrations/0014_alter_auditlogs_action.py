from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apps_audits', '0013_alter_auditlogs_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlogs',
            name='action',
            field=models.CharField(
                choices=[
                    ('CREATE', 'Created'),
                    ('UPDATE', 'Updated'),
                    ('DEACTIVATE', 'Deactivated'),
                    ('STATUS_CHANGE', 'Status changed'),
                    ('SEVERITY_CHANGE', 'Severity changed'),
                    ('CATEGORY_CHANGE', 'Category changed'),
                    ('TRANSFER', 'Report transferred'),
                    ('ACTIVITY_NOTE', 'Report activity recorded'),
                    ('AI_FLAG_DETECTED', 'AI flag detected'),
                    ('AI_FLAG_REVIEW', 'AI flag reviewed'),
                    ('WARNING', 'Warning issued'),
                    ('BAN', 'Account banned'),
                    ('UNBAN', 'Account unbanned'),
                ],
                max_length=50,
            ),
        ),
    ]
