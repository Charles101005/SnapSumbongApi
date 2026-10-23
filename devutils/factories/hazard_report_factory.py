import random
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.reports.models import HazardReports, ReportImages
from .base_factory import SeedData, chance

REPORT_DESCRIPTION_TEMPLATES = [
    "{hazard} along {street}. Visible damage worsening over the past few days, "
    "posing a risk to motorists and pedestrians passing the area.",
    "Reported {hazard} near {street}. Several residents have already "
    "complained about the condition; needs assessment from the city crew.",
    "Observed {hazard} at {street}. The hazard has been present for some time "
    "and appears to have deteriorated after the recent rain.",
    "Complaint about {hazard} at {street}. Traffic slows down in the area "
    "whenever commuters navigate around the obstruction.",
    "{hazard} reported at {street}. Locals are temporarily working around the "
    "hazard but a permanent fix is needed as soon as possible.",
]

HAZARD_PHRASES = [
    "a deep pothole",
    "broken pavement with alligator cracks",
    "a clogged drainage canal",
    "a missing manhole cover",
    "overgrown roadside vegetation blocking the view",
    "faded road markings",
    "a damaged guardrail",
    "dangling utility wires over the road",
    "a flooded street corner",
    "a crumbling road shoulder",
    "an unlit streetlight cluster",
    "garbage overflowing from the collection point",
]


def random_report_description(location: dict | None = None) -> str:
    location = location or random.choice(SeedData.metro_manila_locations())
    street = location["address"].split(",")[0]
    return random.choice(REPORT_DESCRIPTION_TEMPLATES).format(
        hazard=random.choice(HAZARD_PHRASES),
        street=street,
    )


class HazardReportFactory(DjangoModelFactory):
    """Report factory. `category`, `reported_by`, `status` and the final
    lat/lng/address are passed by the seeder; this only fills sensible
    defaults for the rest."""

    class Meta:
        model = HazardReports

    status = HazardReports.Status.NEW
    severity = None
    remarks = None
    resolved_at = None
    confirmed_at = None
    validated_by_name = None
    validated_by = None
    assigned_to = None
    is_anonymous = factory.LazyFunction(lambda: chance(0.2))

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        location = kwargs.pop("_location", None)
        if location is not None:
            kwargs.setdefault(
                "latitude", Decimal(str(location["latitude"]))
            )
            kwargs.setdefault(
                "longitude", Decimal(str(location["longitude"]))
            )
            kwargs.setdefault("address", location["address"])
        kwargs.setdefault(
            "description", random_report_description(location)
        )
        return super()._create(model_class, *args, **kwargs)


class ReportImageFactory(DjangoModelFactory):
    class Meta:
        model = ReportImages

    photo_type = ReportImages.PhotoType.BEFORE
