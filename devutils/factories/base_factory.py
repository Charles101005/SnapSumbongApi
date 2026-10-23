import json
import random
import string
from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from faker import Faker

# Single password used for every generated account. Passes Django's default
# validators plus the app's TraditionalPasswordComplexityValidator (lower,
# upper, digit, special char). Validated again by the command before running.
COMMON_PASSWORD = "SnapSumbong2026!"

# Emails use this domain so --clean can identify command-generated accounts
# without touching manually created dev accounts (e.g. create_initial_admin).
GENERATED_EMAIL_DOMAIN = "@snapsumbong-dev.test"

DATA_DIR = Path(settings.BASE_DIR) / "devutils" / "data"

_faker = Faker("en_PH")

# Filipino name pools (en_PH locale still returns Western names, so use
# built-in lists for realistic local names).
FILIPINO_MALE_NAMES = [
    "Juan", "Pedro", "Miguel", "Jose", "Angelo", "Ryan", "Christian",
    "Joshua", "Nathaniel", "Carlo", "Rafael", "Emiliano", "Danilo",
    "Rolando", "Ernesto", "Fernando", "Gabriel", "Hector", "Ismael",
    "Jerome", "Kevin", "Lloyd", "Marvin", "Nestor", "Oscar", "Pablo",
    "Ramon", "Sergio", "Tomas", "Vicente", "Arnel", "Benedict",
    "Cedric", "Dennis", "Elmer", "Aldrin",
]
FILIPINO_FEMALE_NAMES = [
    "Maria", "Ana", "Rosa", "Liza", "Angelica", "Jasmine", "Kristine",
    "Marites", "Jennylyn", "Patricia", "Abigail", "Camille", "Diana",
    "Elena", "Fatima", "Grace", "Hannah", "Irene", "Joyce", "Karen",
    "Lorna", "Michelle", "Nora", "Olivia", "Pearl", "Queenie",
    "Rachel", "Sarah", "Teresa", "Vanessa", "Bianca", "Charlene",
    "Daniela", "Erika", "Fiona", "Geraldine",
]
FILIPINO_LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia",
    "Mendoza", "Torres", "Andrada", "Villanueva", "Ramos", "Castillo",
    "Aquino", "Fernandez", "Gonzales", "Lopez", "Navarro", "Padilla",
    "Perez", "Dizon", "Mercado", "Aguilar", "Cabrera", "Espinosa",
    "Faustino", "Gutierrez", "Hernandez", "Ignacio", "Jimenez",
    "Manalo", "Panganiban", "Salazar", "Villafuerte", "Dela Rosa",
    "Alcantara", "Bermudez",
]


def chance(probability: float) -> bool:
    return random.random() < probability


def pick(seq):
    return random.choice(seq)


def random_filipino_name(sex: str | None = None) -> tuple[str, str]:
    """Return (first_name, last_name), optionally sex-constrained."""
    if sex == "M":
        first = pick(FILIPINO_MALE_NAMES)
    elif sex == "F":
        first = pick(FILIPINO_FEMALE_NAMES)
    else:
        first = pick(FILIPINO_MALE_NAMES + FILIPINO_FEMALE_NAMES)
    return first, pick(FILIPINO_LAST_NAMES)


def random_middle_name() -> str:
    first, _ = random_filipino_name()
    return first


def random_ph_phone() -> str:
    """11-digit PH mobile format: 09XXXXXXXXX."""
    return "09" + "".join(random.choice(string.digits) for _ in range(9))


def random_birth_date(min_age: int, max_age: int) -> date:
    days = random.randint(min_age * 365, max_age * 365)
    return date.today() - timedelta(days=days)


def random_gender() -> str:
    return random.choices(
        ["M", "F", "O"], weights=[47, 48, 5], k=1
    )[0]


def random_last_active() -> datetime | None:
    """Some users have a recent activity timestamp, others never logged in."""
    if chance(0.6):
        days_ago = random.randint(0, 45)
        hours_ago = random.randint(0, 23)
        return timezone.now() - timedelta(days=days_ago, hours=hours_ago)
    return None


def slugify_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def load_data_file(name: str):
    """Load and cache a JSON file from devutils/data/."""
    path = DATA_DIR / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class SeedData:
    """Lazy cached access to the split reference data files."""

    _cache: dict = {}

    @classmethod
    def geo_codes(cls) -> list[dict]:
        if "geo" not in cls._cache:
            cls._cache["geo"] = load_data_file("ph_geo_codes.json")
        return cls._cache["geo"]

    @classmethod
    def locations(cls) -> dict:
        if "loc" not in cls._cache:
            cls._cache["loc"] = load_data_file("ph_locations.json")
        return cls._cache["loc"]

    @classmethod
    def metro_manila_locations(cls) -> list[dict]:
        return cls.locations()["metro_manila"]

    @classmethod
    def outside_metro_manila_locations(cls) -> list[dict]:
        return cls.locations()["outside_metro_manila"]

    @classmethod
    def image_urls(cls) -> dict:
        if "img" not in cls._cache:
            cls._cache["img"] = load_data_file("image_urls.json")
        return cls._cache["img"]

    @classmethod
    def pfp_urls(cls) -> list[str]:
        if "pfp" not in cls._cache:
            cls._cache["pfp"] = load_data_file("user_pfp_urls.json")
        return cls._cache["pfp"]


def random_geo_code_entry() -> dict:
    """One entry with region/province/city/barangay codes + street address."""
    return pick(SeedData.geo_codes())
