from django.db import models

class Permissions(models.Model):
    permission_id = models.AutoField(primary_key=True)

    permission_name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=150)
    module = models.CharField(max_length=50)
