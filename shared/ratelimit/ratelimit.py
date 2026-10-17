from dataclasses import dataclass

from .base_ratelimit import RateLimitConfig


@dataclass(frozen=True)
class AnonRateLimit(RateLimitConfig):
    rate: int = 20
    period: int = 60


@dataclass(frozen=True)
class StandardRateLimit(RateLimitConfig):
    rate: int = 60
    period: int = 60


@dataclass(frozen=True)
class StrictRateLimit(RateLimitConfig):
    rate: int = 5
    period: int = 60
