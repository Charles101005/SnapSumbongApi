from django.db import migrations


def _link_permission(apps, operation):
    Roles = apps.get_model("apps_accounts", "Roles")
    Permissions = apps.get_model("apps_accounts", "Permissions")

    role = Roles.objects.filter(role_code="SUPERVISOR").first()
    permission = Permissions.objects.filter(permission_name="user:read_all").first()

    if role is None or permission is None:
        return

    operation(role, permission)


def remove_supervisor_user_read_all(apps, schema_editor):
    _link_permission(apps, lambda role, permission: role.permissions.remove(permission))


def restore_supervisor_user_read_all(apps, schema_editor):
    _link_permission(apps, lambda role, permission: role.permissions.add(permission))


class Migration(migrations.Migration):

    dependencies = [
        ("apps_accounts", "0018_citizenwarnings"),
    ]

    operations = [
        migrations.RunPython(
            remove_supervisor_user_read_all,
            restore_supervisor_user_read_all,
        ),
    ]
