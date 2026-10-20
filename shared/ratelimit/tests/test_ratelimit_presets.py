import pytest

from shared.ratelimit import (
    AnonRateLimit,
    RateLimitConfig,
    StandardRateLimit,
    StrictRateLimit,
)


@pytest.mark.parametrize(
    "cls,expected_rate,expected_period",
    [
        (AnonRateLimit, 20, 60),
        (StandardRateLimit, 60, 60),
        (StrictRateLimit, 10, 60),
    ],
)
def test_preset_defaults(cls, expected_rate, expected_period):
    config = cls()

    assert isinstance(config, RateLimitConfig)
    assert config.rate == expected_rate
    assert config.period == expected_period


def test_preset_with_overrides_creates_same_type():
    strict = StrictRateLimit()

    overridden = strict.with_(rate=99)

    assert isinstance(overridden, StrictRateLimit)
    assert overridden.rate == 99
    assert overridden.period == strict.period
