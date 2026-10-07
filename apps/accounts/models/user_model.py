from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models

from .role_model import Roles
from shared.utils import model_number_generator


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

    def get_by_active_id_or_none(self, user_id: int) -> 'Users|None':
        return self.filter(
            user_id=user_id,
            is_active=True,
        ).first()


class Users(AbstractBaseUser):
    class GenderChoices(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    user_id = models.AutoField(primary_key=True)
    user_number = models.CharField(max_length=20, unique=True, editable=False, db_index=True)

    last_name = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)

    email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=11, blank=True, null=True)
    profile_picture = models.URLField(max_length=500, blank=True, null=True)
    birth_date = models.DateField(null=True)
    gender = models.CharField(max_length=1, choices=GenderChoices.choices, null=True)
    street_address = models.CharField(max_length=255, null=True)

    region_code = models.CharField(max_length=10, null=True)
    province_code = models.CharField(max_length=10, null=True)
    city_code = models.CharField(max_length=10, null=True)
    barangay_code = models.CharField(max_length=10, null=True)

    is_notified = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True) ##
    is_staff = models.BooleanField(default=False) ##

    must_change_password = models.BooleanField(default=False)

    role = models.ForeignKey(Roles, on_delete=models.PROTECT)

    last_active = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    USERNAME_FIELD = 'email'

    objects = UserManager()

    @property
    def full_name(self) -> str:
        middle_name = f" {self.middle_name[0].upper()}." if self.middle_name else ""
        return f"{self.last_name}, {self.first_name}" + middle_name

    def get_full_name(self) -> str:
        middle_name = f" {self.middle_name[0].upper()}." if self.middle_name else ""
        return f"{self.last_name}, {self.first_name}" + middle_name

    def save(self, *args, **kwargs):
        if not self.user_number:
            self.user_number = model_number_generator("USER")

            while Users.objects.filter(user_number=self.user_number).exists():
                self.user_number = model_number_generator("USER")

        super().save(**kwargs)

    def __str__(self):
        return self.email
