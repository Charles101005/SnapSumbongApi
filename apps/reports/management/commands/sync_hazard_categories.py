from django.core.management.base import BaseCommand

from apps.reports.constants import AllHazardCategory
from apps.reports.models import HazardCategories


class Command(BaseCommand):
    def handle(self, *args, **options):
        all_hazard_category_definitions = AllHazardCategory.get_flat_list()

        for category in all_hazard_category_definitions:
            HazardCategories.objects.update_or_create(
                hazard_name=category.hazard_name,
                defaults={
                    'description': category.description,
                    'response_time_days': category.response_time_days
                }
            )

        active_hazard_category_names = [category.hazard_name for category in all_hazard_category_definitions]

        deleted_count, _ = HazardCategories.objects.exclude(hazard_name__in=active_hazard_category_names).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Synced {len(active_hazard_category_names)} categories. Deleted {deleted_count} categories."
        ))