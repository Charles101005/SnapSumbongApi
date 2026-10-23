from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.accounts.models import CitizenWarnings, Roles, Users
from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports, ReportImages
from devutils.factories.base_factory import GENERATED_EMAIL_DOMAIN
from devutils.seeders.base_seeder import Progress

# The 4 default roles are synced by sync_db/sync_initial_roles and are never
# removed, even by --clean.
DEFAULT_ROLE_CODES = ("SYSTEM_ADMIN", "SUPERVISOR", "REPORT_OFFICER", "CITIZEN")


def generated_users_qs():
    return Users.objects.filter(email__endswith=GENERATED_EMAIL_DOMAIN)


def _blueprint_role_filter():
    """Q matching the custom-role codes this command creates (blueprints and
    their numbered variants, e.g. FIELD_ENGINEER / FIELD_ENGINEER_2)."""
    from devutils.seeders.user_seeder import CUSTOM_ROLE_BLUEPRINTS

    q = Q()
    for name, _ in CUSTOM_ROLE_BLUEPRINTS:
        base = Roles.format_role_code(name)
        q |= Q(role_code=base) | Q(role_code__startswith=f"{base}_")
    return q


def has_generated_data() -> bool:
    """True when a previous generate_dummy_data run left data behind."""
    if generated_users_qs().exists():
        return True
    return Roles.objects.exclude(
        role_code__in=DEFAULT_ROLE_CODES
    ).filter(_blueprint_role_filter()).exists()


def clean_dummy_data(progress: Progress) -> None:
    """Remove previously seeded dummy data, leaving default data intact.

    Only accounts created by this command (identified by the generated email
    domain) are removed, so manually created dev accounts (e.g. from
    create_initial_admin) survive a --clean run.
    """
    generated = generated_users_qs()
    report_ids = list(
        HazardReports.objects.filter(reported_by__in=generated)
        .values_list("report_id", flat=True)
    )
    user_ids = list(generated.values_list("user_id", flat=True))

    warnings_deleted, _ = CitizenWarnings.objects.filter(
        user_id__in=user_ids
    ).delete()

    # Audit logs do not cascade through the GenericForeignKey: remove the
    # ones written by generated actors AND the system-actor (user=NULL)
    # events that target generated reports/users.
    report_ct = ContentType.objects.get_for_model(HazardReports)
    user_ct = ContentType.objects.get_for_model(Users)
    logs_deleted, _ = AuditLogs.objects.filter(
        Q(user_id__in=user_ids)
        | Q(content_type=report_ct, object_id__in=report_ids)
        | Q(content_type=user_ct, object_id__in=user_ids)
    ).delete()

    reports_deleted, report_details = HazardReports.objects.filter(
        report_id__in=report_ids
    ).delete()
    # ReportImages cascade with their reports; report_details tracks them.

    users_deleted, _ = Users.objects.filter(user_id__in=user_ids).delete()

    # Custom roles (not default, not protected) with no remaining users.
    removable_roles = Roles.objects.exclude(
        role_code__in=DEFAULT_ROLE_CODES
    ).filter(is_protected=False)
    roles_deleted = 0
    for role in removable_roles:
        if not role.users.exists():
            role.delete()
            roles_deleted += 1

    progress.done(
        f"Removed {users_deleted} users, {reports_deleted} reports "
        f"(+{report_details.get('reports.ReportImages', 0)} images), "
        f"{warnings_deleted} warnings, {logs_deleted} audit logs, "
        f"{roles_deleted} custom roles"
    )
