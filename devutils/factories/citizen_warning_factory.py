import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import CitizenWarnings
from .base_factory import pick

WARNING_REASONS = [
    "Repeatedly submitted hoax hazard reports that could not be verified on site.",
    "Submitted a misleading photo unrelated to the reported location.",
    "Abusive language directed at responding personnel during report follow-up.",
    "Duplicate spam submissions flooding the report queue.",
    "Report was flagged as invalid by verification and matches previous prank submissions.",
    "Deliberately altered report details after staff reached out for clarification.",
    "Used the platform to advertise unrelated services instead of reporting hazards.",
]


class CitizenWarningFactory(DjangoModelFactory):
    class Meta:
        model = CitizenWarnings

    reason = factory.LazyFunction(lambda: pick(WARNING_REASONS))

    # Optional link to an INVALID report; the seeder passes it when the
    # warning should reference one (ModerationService rules apply).
    report = None
