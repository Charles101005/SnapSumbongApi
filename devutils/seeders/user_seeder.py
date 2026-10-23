import random
import string
from dataclasses import dataclass, field

from django.utils import timezone

from apps.accounts.models import Users, Roles, Permissions
from devutils.factories import CitizenUserFactory, StaffUserFactory
from devutils.factories.base_factory import (
    COMMON_PASSWORD,
    GENERATED_EMAIL_DOMAIN,
    chance,
    pick,
)
from devutils.seeders.base_seeder import (
    AuditEvent,
    AuditEventCollector,
    Progress,
    backdate,
    reissue_number,
)


@dataclass
class UserSeedResult:
    system_admins: list = field(default_factory=list)
    supervisors: list = field(default_factory=list)
    report_officers: list = field(default_factory=list)
    citizens: list = field(default_factory=list)          # active citizens only
    deactivated_citizens: list = field(default_factory=list)
    custom_roles: list = field(default_factory=list)
    all_staff: list = field(default_factory=list)

    @property
    def warn_actors(self) -> list:
        """Staff allowed to issue warnings (SYSTEM_ADMIN + SUPERVISOR have USERS.WARN)."""
        return self.system_admins + self.supervisors

    @property
    def assignment_pool(self) -> list:
        """Active staff eligible for report assignment (REPORT_OFFICER)."""
        return [u for u in self.report_officers if u.is_active]


CUSTOM_ROLE_BLUEPRINTS = [
    ("Field Engineer", "Inspects and validates reported road hazards on site."),
    ("Dispatch Clerk", "Coordinates crew dispatch and equipment scheduling."),
    ("Data Analyst", "Reviews report metrics and compliance scoring."),
    ("Community Liaison", "Handles resident follow-ups and confirmations."),
    ("Safety Inspector", "Conducts safety audits of completed rectification works."),
    ("Records Officer", "Maintains report documentation and photolog archives."),
]

STAFF_UPDATE_NOTE = "Updated contact number as per personnel records."


def run(
    *,
    progress: Progress,
    events: AuditEventCollector,
    counts: dict,
    password: str | None = None,
) -> UserSeedResult:
    result = UserSeedResult()
    password = password or COMMON_PASSWORD

    roles = {
        code: Roles.objects.get(role_code=code)
        for code in ("SYSTEM_ADMIN", "SUPERVISOR", "REPORT_OFFICER", "CITIZEN")
    }

    # --- first admin mirrors create_initial_admin: no audit event ---------
    admin_count = max(1, counts["system_admins"])
    first_admin = StaffUserFactory(role=roles["SYSTEM_ADMIN"], raw_password=password)
    _backdate_user(first_admin, min_days=180, max_days=365)
    result.system_admins.append(first_admin)
    result.all_staff.append(first_admin)
    progress.step(f"Created SYSTEM_ADMIN #1: {first_admin.email} (bootstrap)")

    # --- custom roles (optional) ------------------------------------------
    for i in range(counts["custom_roles"]):
        name, description = CUSTOM_ROLE_BLUEPRINTS[i % len(CUSTOM_ROLE_BLUEPRINTS)]
        if i >= len(CUSTOM_ROLE_BLUEPRINTS):
            name = f"{name} {i // len(CUSTOM_ROLE_BLUEPRINTS) + 1}"
        role_code = Roles.format_role_code(name)
        # A same-coded role may survive --clean when manually assigned users;
        # keep seeding instead of tripping the unique constraint.
        if Roles.objects.filter(role_code=role_code).exists():
            suffix = 2
            while Roles.objects.filter(
                role_code=f"{role_code}_{suffix}"
            ).exists():
                suffix += 1
            role_code = f"{role_code}_{suffix}"
        role = Roles.objects.create(
            role_name=name,
            role_code=role_code,
            description=description,
            is_protected=False,
        )
        perms = random.sample(list(Permissions.objects.all()), k=random.randint(2, 6))
        role.permissions.set(perms)
        created_at = _past(90, 300)
        backdate(role, created_at, ["created_at", "updated_at"])
        result.custom_roles.append(role)
        events.add(AuditEvent(
            occurred_at=created_at,
            action="CREATE",
            module="ROLE",
            actor=first_admin,
            target=role,
            description=f"ROLE {role.role_code}({role.role_id}) was created by {first_admin.user_number}",
            payload={
                "role_details": {
                    "role_id": role.role_id,
                    "role_code": role.role_code,
                    "role_name": role.role_name,
                    "description": role.description,
                },
                "initial_permissions": [p.permission_name for p in perms],
            },
        ))
        progress.step(f"Created custom role: {role.role_code}")

    # Deactivate the last custom role (only if it has no users) so an
    # inactive role state exists in the data.
    deactivated_role = None
    if len(result.custom_roles) >= 2:
        deactivated_role = result.custom_roles[-1]

    # --- remaining default-role staff -------------------------------------
    def make_staff(role, tag, target_list, min_days=60, max_days=240):
        user = StaffUserFactory(role=role, raw_password=password)
        created_at = _past(min_days, max_days)
        _backdate_user(user, min_days, max_days, when=created_at)
        target_list.append(user)
        result.all_staff.append(user)
        events.add(AuditEvent(
            occurred_at=created_at,
            action="CREATE",
            module="EMPLOYEE",
            actor=first_admin,
            target=user,
            description=f"EMPLOYEE {user.user_number} was created by {first_admin.user_number}",
            payload={
                "assigned_role": {
                    "role_id": role.role_id,
                    "role_code": role.role_code,
                    "role_name": role.role_name,
                }
            },
        ))
        progress.step(f"Created {tag}: {user.email}")
        return user

    for _ in range(admin_count - 1):
        make_staff(roles["SYSTEM_ADMIN"], "SYSTEM_ADMIN", result.system_admins)
    for _ in range(counts["supervisors"]):
        make_staff(roles["SUPERVISOR"], "SUPERVISOR", result.supervisors)
    for _ in range(counts["report_officers"]):
        make_staff(roles["REPORT_OFFICER"], "REPORT_OFFICER", result.report_officers)

    # Staff assigned to custom roles (1 per custom role; excluded from role
    # roles kept above so the deactivated custom role stays user-less).
    assignable_roles = (
        result.custom_roles[:-1] if deactivated_role else result.custom_roles
    )
    for role in assignable_roles:
        make_staff(role, f"custom role {role.role_code}", result.all_staff)

    # --- citizens ----------------------------------------------------------
    for i in range(counts["citizens"]):
        citizen = CitizenUserFactory(role=roles["CITIZEN"], raw_password=password)
        _backdate_user(citizen, 30, 365)
        result.citizens.append(citizen)
        if (i + 1) % 10 == 0 or i == counts["citizens"] - 1:
            progress.step(f"Created citizens: {i + 1}/{counts['citizens']}")

    # --- varied user states -------------------------------------------------
    # A couple of citizens deactivated through moderation-style update.
    deactivate_count = min(2, max(0, len(result.citizens) // 8))
    for _ in range(deactivate_count):
        citizen = result.citizens.pop()
        citizen.is_active = False
        citizen.save(update_fields=["is_active", "updated_at"])
        at = _past(5, 40)
        backdate(citizen, at, ["updated_at"])
        result.deactivated_citizens.append(citizen)
        events.add(AuditEvent(
            occurred_at=at,
            action="DEACTIVATE",
            module="USER",
            actor=first_admin,
            target=citizen,
            description=f"{citizen.user_number} was deactivated by {first_admin.user_number}",
            payload={"changes": {"is_active": {"from": True, "to": False}}},
        ))
        progress.step(f"Deactivated citizen: {citizen.email}")

    # One staff info update (UPDATE action coverage).
    if result.report_officers:
        target_staff = pick(result.report_officers)
        old_contact = target_staff.contact_number
        target_staff.contact_number = "09" + "".join(
            random.choice(string.digits) for _ in range(9)
        )
        target_staff.save(update_fields=["contact_number", "updated_at"])
        at = _past(3, 30)
        backdate(target_staff, at, ["updated_at"])
        events.add(AuditEvent(
            occurred_at=at,
            action="UPDATE",
            module="EMPLOYEE",
            actor=first_admin,
            target=target_staff,
            description=(
                f"EMPLOYEE {target_staff.user_number} was updated by "
                f"{first_admin.user_number} (fields: contact_number)"
            ),
            payload={"changes": {"contact_number": {"from": old_contact, "to": target_staff.contact_number}}},
        ))
        progress.detail(f"Updated contact for {target_staff.user_number}")

    # One staff deactivation (DEACTIVATE EMPLOYEE coverage).
    if len(result.supervisors) >= 1 and counts["supervisors"] >= 2:
        decoy = result.supervisors.pop()
        decoy.is_active = False
        decoy.save(update_fields=["is_active", "updated_at"])
        at = _past(3, 25)
        backdate(decoy, at, ["updated_at"])
        events.add(AuditEvent(
            occurred_at=at,
            action="DEACTIVATE",
            module="EMPLOYEE",
            actor=first_admin,
            target=decoy,
            description=(
                f"EMPLOYEE {decoy.user_number} was deactivated by "
                f"{first_admin.user_number}"
            ),
            payload={"changes": {"is_active": {"from": True, "to": False}}},
        ))
        progress.step(f"Deactivated supervisor: {decoy.email}")

    # Deactivate the spare custom role now (no users attached).
    if deactivated_role is not None:
        deactivated_role.is_active = False
        deactivated_role.save(update_fields=["is_active", "updated_at"])
        at = _past(2, 20)
        backdate(deactivated_role, at, ["updated_at"])
        events.add(AuditEvent(
            occurred_at=at,
            action="DEACTIVATE",
            module="ROLE",
            actor=first_admin,
            target=deactivated_role,
            description=(
                f"ROLE {deactivated_role.role_code} was deactivated by "
                f"{first_admin.user_number}"
            ),
            payload={"changes": {"is_active": {"from": True, "to": False}}},
        ))
        progress.step(f"Deactivated custom role: {deactivated_role.role_code}")

    progress.done(
        f"{len(result.all_staff)} staff, {len(result.citizens)} active citizens, "
        f"{len(result.deactivated_citizens)} deactivated, "
        f"{len(result.custom_roles)} custom roles"
    )
    return result


# ---------------------------------------------------------------------------

def _past(min_days: int, max_days: int):
    from devutils.seeders.base_seeder import random_past_datetime
    return random_past_datetime(min_days, max_days)


def _backdate_user(user: Users, min_days: int, max_days: int, when=None) -> None:
    when = when or _past(min_days, max_days)
    backdate(user, when, ["created_at", "updated_at"])
    reissue_number(user, "user_number", "USER", when)
    user.save(update_fields=["user_number"])
