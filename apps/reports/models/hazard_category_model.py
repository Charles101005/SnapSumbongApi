from django.db import models


class HazardCategoriesManager(models.Manager):
    def get_by_id_or_none(self, hazard_id: int) -> 'HazardCategories|None':
        return self.filter(hazard_id=hazard_id).first()


class HazardCategories(models.Model):
    hazard_id = models.AutoField(primary_key=True)
    hazard_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    response_time_days = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)


    objects = HazardCategoriesManager()