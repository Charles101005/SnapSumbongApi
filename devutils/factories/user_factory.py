import itertools

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Users
from .base_factory import (
    COMMON_PASSWORD,
    GENERATED_EMAIL_DOMAIN,
    SeedData,
    chance,
    pick,
    random_birth_date,
    random_filipino_name,
    random_geo_code_entry,
    random_gender,
    random_last_active,
    random_middle_name,
    random_ph_phone,
    slugify_name,
)


class UserFactory(DjangoModelFactory):
    """Base user factory; role must be passed by the seeder."""

    class Meta:
        model = Users
        exclude = ("raw_password",)

    raw_password = COMMON_PASSWORD

    first_name = factory.LazyFunction(lambda: random_filipino_name()[0])
    last_name = factory.LazyFunction(lambda: random_filipino_name()[1])
    middle_name = factory.LazyFunction(
        lambda: random_middle_name() if chance(0.7) else None
    )

    email = factory.LazyAttribute(
        lambda o: (
            f"{slugify_name(o.first_name)}.{slugify_name(o.last_name)}"
            f"{UserFactory._next_seq()}{GENERATED_EMAIL_DOMAIN}"
        )
    )

    is_notified = factory.LazyFunction(lambda: chance(0.7))
    is_active = True
    last_active = factory.LazyFunction(random_last_active)

    _seq = itertools.count(1)

    @classmethod
    def _next_seq(cls) -> int:
        return next(cls._seq)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        raw_password = kwargs.pop("raw_password", COMMON_PASSWORD)
        user = model_class.objects.create_user(
            password=raw_password,
            **kwargs,
        )
        return user


class CitizenUserFactory(UserFactory):
    """Citizens: all address/contact fields are optional and random."""

    is_staff = False
    must_change_password = False

    contact_number = factory.LazyFunction(
        lambda: random_ph_phone() if chance(0.75) else None
    )
    birth_date = factory.LazyFunction(
        lambda: random_birth_date(18, 70) if chance(0.8) else None
    )
    gender = factory.LazyFunction(
        lambda: random_gender() if chance(0.85) else None
    )

    # Address block: randomly present or entirely null (citizens only ~50%
    # fill this in, mirroring real incomplete profiles).
    street_address = None
    region_code = None
    province_code = None
    city_code = None
    barangay_code = None
    profile_picture = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # NOTE: direct assignment, not setdefault — the =None class
        # attributes above are plain-value declarations and factory_boy
        # always passes them in kwargs, so setdefault would never fire.
        if chance(0.5):
            entry = random_geo_code_entry()
            kwargs["street_address"] = entry["street_address"]
            kwargs["region_code"] = entry["region_code"]
            kwargs["province_code"] = entry["province_code"]
            kwargs["city_code"] = entry["city_code"]
            kwargs["barangay_code"] = entry["barangay_code"]
        if chance(0.35):
            kwargs["profile_picture"] = pick(SeedData.pfp_urls())
        return super()._create(model_class, *args, **kwargs)


class StaffUserFactory(UserFactory):
    """Staff: address/contact fields are REQUIRED (mirrors UserService.create_staff)."""

    is_staff = True
    must_change_password = factory.LazyFunction(lambda: chance(0.4))

    contact_number = factory.LazyFunction(random_ph_phone)
    birth_date = factory.LazyFunction(lambda: random_birth_date(22, 60))
    gender = factory.LazyFunction(random_gender)

    street_address = factory.LazyFunction(
        lambda: random_geo_code_entry()["street_address"]
    )
    region_code = factory.LazyFunction(
        lambda: random_geo_code_entry()["region_code"]
    )
    province_code = factory.LazyFunction(
        lambda: random_geo_code_entry()["province_code"]
    )
    city_code = factory.LazyFunction(
        lambda: random_geo_code_entry()["city_code"]
    )
    barangay_code = factory.LazyFunction(
        lambda: random_geo_code_entry()["barangay_code"]
    )

    profile_picture = factory.LazyFunction(
        lambda: pick(SeedData.pfp_urls()) if chance(0.3) else None
    )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Keep the whole address block on ONE geo entry so codes and street
        # address describe the same place.
        entry = random_geo_code_entry()
        kwargs["street_address"] = entry["street_address"]
        kwargs["region_code"] = entry["region_code"]
        kwargs["province_code"] = entry["province_code"]
        kwargs["city_code"] = entry["city_code"]
        kwargs["barangay_code"] = entry["barangay_code"]
        return super()._create(model_class, *args, **kwargs)
