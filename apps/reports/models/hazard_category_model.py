from django.db import models


class HazardCategoriesManager(models.Manager):
    def get_by_id_or_none(self, hazard_id: int) -> 'HazardCategories|None':
        return self.filter(pk=hazard_id).first()

    def get_by_active_id_or_none(self, hazard_id: int) -> 'HazardCategories|None':
        return self.filter(pk=hazard_id, is_active=True).first()


class HazardCategories(models.Model):
    hazard_id = models.AutoField(primary_key=True)
    hazard_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)


    objects = HazardCategoriesManager()