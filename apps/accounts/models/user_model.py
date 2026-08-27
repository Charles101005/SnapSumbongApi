from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models

from .role_model import Roles


class UserManager(BaseUserManager):
    def create_user(
            self,
            *,
            email: str,
            role: Roles,
            first_name: str,
            last_name: str,
            middle_name: str|None = None,

            password: str|None = None,
            password_hash: str|None = None,
            **extra_fields
    ) -> 'Users':
        if (password is None) == (password_hash is None):
            raise ValueError('Provide only one password type')

        normalized_email = self.normalize_email(email)

        user = self.model(
            email=normalized_email,
            role=role,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            **extra_fields
        )

        if password_hash is not None:
            user.password = password_hash
        else:
            user.set_password(password)

        user.save(using=self._db)

        return user

    def get_by_active_email_or_none(self, email: str) -> 'Users|None':
        return self.filter(
            email__iexact=self.normalize_email(email),
            is_active=True,
        ).first()


class Users(AbstractBaseUser):
    user_id = models.AutoField(primary_key=True)

    last_name = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)

    email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=11, blank=True, null=True)
    profile_picture = models.URLField(blank=True, null=True)

    is_notified = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True) ##
    is_staff = models.BooleanField(default=False) ##

    role = models.ForeignKey(Roles, on_delete=models.PROTECT)

    last_active = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    USERNAME_FIELD = 'email'

    objects = UserManager()

    def __str__(self):
        return self.email
