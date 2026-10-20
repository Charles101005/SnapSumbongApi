from django.db import migrations


def _grant_supervisor_report_assign(apps, schema_editor):
    Roles = apps.get_model("apps_accounts", "Roles")
    Permissions = apps.get_model("apps_accounts", "Permissions")

    role = Roles.objects.filter(role_code="SUPERVISOR").first()
    if role is None:
        return

    permission, _ = Permissions.objects.get_or_create(
        permission_name="report:assign",
        defaults={
            "description": "Allows the role to TRANSFER hazard reports to another officer",
            "module": "reports",
        },
    )

    role.permissions.add(permission)


def _revoke_supervisor_report_assign(apps, schema_editor):
    Roles = apps.get_model("apps_accounts", "Roles")
    Permissions = apps.get_model("apps_accounts", "Permissions")

    role = Roles.objects.filter(role_code="SUPERVISOR").first()
    permission = Permissions.objects.filter(permission_name="report:assign").first()

    if role is None or permission is None:
        return

    role.permissions.remove(permission)


class Migration(migrations.Migration):

    dependencies = [
        ("apps_accounts", "0019_drop_supervisor_user_read_all"),
    ]

    operations = [
        migrations.RunPython(
            _grant_supervisor_report_assign,
            _revoke_supervisor_report_assign,
        ),
    ]
