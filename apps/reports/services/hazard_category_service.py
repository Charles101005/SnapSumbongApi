from apps.reports.models import HazardCategories
from shared.results import DomainResult


class HazardCategoryService:
    @staticmethod
    def get_all_category() -> DomainResult[HazardCategories]:
        all_hazard_categories = HazardCategories.objects.all()

        return DomainResult.success(all_hazard_categories)
