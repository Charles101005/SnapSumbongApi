import factory
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from apps.reports.models import HazardReports, HazardCategories


class HazardCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HazardCategories

    hazard_name = factory.Sequence(lambda n: f"Test Category {n}")
    description = "Test hazard category"
    response_time_days = 3
    is_active = True


class HazardReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HazardReports

    category = factory.SubFactory(HazardCategoryFactory)
    latitude = Decimal("14.599500")
    longitude = Decimal("120.984200")
    address = "Sampaloc, Manila, Metro Manila"
    description = "Test road defect description"
    status = HazardReports.Status.NEW
    due_at = factory.LazyAttribute(
        lambda obj: timezone.now() + timedelta(days=obj.category.response_time_days)
    )
