from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apps_accounts', '0018_citizenwarnings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='verificationrequest',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('REGISTRATION', 'Registration'),
                    ('FORGOT_PASSWORD', 'Forgot Password'),
                    ('EMAIL_CHANGE', 'Email Change'),
                ],
                max_length=30,
            ),
        ),
    ]
