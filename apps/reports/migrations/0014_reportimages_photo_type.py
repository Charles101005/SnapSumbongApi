from django.db import migrations, models


def forwards_is_resolution_to_photo_type(apps, schema_editor):
    ReportImages = apps.get_model('apps_reports', 'ReportImages')
    ReportImages.objects.filter(is_resolution=True).update(photo_type='AFTER')
    ReportImages.objects.filter(is_resolution=False).update(photo_type='BEFORE')


def backwards_photo_type_to_is_resolution(apps, schema_editor):
    ReportImages = apps.get_model('apps_reports', 'ReportImages')
    ReportImages.objects.filter(photo_type='AFTER').update(is_resolution=True)
    # BEFORE and DURING both collapse into is_resolution=False on the way back;
    # DURING photos predate the old schema so there is no exact inverse.
    ReportImages.objects.filter(photo_type__in=['BEFORE', 'DURING']).update(is_resolution=False)


class Migration(migrations.Migration):

    dependencies = [
        ('apps_reports', '0013_hazardreports_due_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportimages',
            name='photo_type',
            field=models.CharField(
                choices=[('BEFORE', 'Before'), ('DURING', 'During'), ('AFTER', 'After')],
                db_index=True,
                default='BEFORE',
                max_length=10,
            ),
        ),
        migrations.RunPython(
            forwards_is_resolution_to_photo_type,
            backwards_photo_type_to_is_resolution,
        ),
        migrations.RemoveField(
            model_name='reportimages',
            name='is_resolution',
        ),
    ]
