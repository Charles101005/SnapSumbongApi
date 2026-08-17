from django.db import models

from .permission_model import Permissions


class RoleManager(models.Manager):
    def get_by_id_or_none(self, role_id: int) -> 'Roles|None':
        return self.filter(pk=role_id).first()

    def get_by_code_or_none(self, code: str) -> 'Roles|None':
        return self.filter(role_code=code).first()


class Roles(models.Model):
    role_id = models.AutoField(primary_key=True)

    role_code = models.CharField(max_length=50, unique=True) ##
    role_name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200)
    is_protected = models.BooleanField(default=False) ##

    permissions = models.ManyToManyField(Permissions, related_name='roles')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = RoleManager()