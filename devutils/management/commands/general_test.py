from django.db.models import Count, F

from apps.accounts.models import Users
from devutils.base import DebugOnlyCommand
from shared.authorization import AllPermissions


class Command(DebugOnlyCommand):

    def handle(self, *args, **options):
        # users = Users.objects.filter(
        #     is_staff=True,
        #     is_active=True,
        #     role__permissions__permission_name=AllPermissions.REPORTS.UPDATE_ASSIGNED.name,
        # )
        #
        # for user in users:
        #     user.is_active = False
        #     user.save()




        # users = Users.objects.filter(
        #     is_staff=True,
        #     is_active=True,
        #     role__permissions__permission_name=AllPermissions.REPORTS.UPDATE_ASSIGNED.name,
        # ).annotate(
        #     report_count=Count('assigned_hazard_reports'),
        # ).distinct().order_by(
        #     F('assigned_at').asc(nulls_first=True),
        #     'created_at',
        #     'user_id',
        # )
        #
        # if not users.exists():
        #     self.stdout.write("No staff are eligible for automatic assignment.")
        #     return
        #
        # self.stdout.write(
        #     "user_number : full_name : assigned_at : created_at : assigned_reports"
        # )
        #
        # for user in users:
        #     self.stdout.write(
        #         f"{user.user_number} : {user.full_name} : {user.assigned_at} : "
        #         f"{user.created_at} : {user.report_count}"
        #     )
        #
        # chosen = users.first()
        # self.stdout.write(
        #     "\tCHOSEN:"
        #     f"{chosen.user_number} : {chosen.full_name} : {chosen.assigned_at} : "
        #     f"{chosen.created_at} : {chosen.report_count}"
        # )
        pass