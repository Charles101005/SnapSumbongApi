from django.db import models
from django.db.models import QuerySet


class HazardCategoriesManager(models.Manager):
    def get_by_ids_or_none(self, hazard_ids: list[int]) -> 'QuerySet[HazardCategories]|None':
        existing_ids = set(
            self.filter(hazard_id__in=hazard_ids).values_list('hazard_id', flat=True)
        )

        if len(existing_ids) != len(set(hazard_ids)):
            return None
        return self.filter(hazard_id__in=hazard_ids)


class HazardCategories(models.Model):
    hazard_id = models.AutoField(primary_key=True)
    hazard_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    response_time = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)


    objects = HazardCategoriesManager()