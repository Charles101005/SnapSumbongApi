from dataclasses import dataclass, replace

from django.core.cache import cache
from rest_framework.request import Request
from rest_framework.exceptions import Throttled


_PERIOD_UNITS: dict[str, int] = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "h": 3600,
    "hour": 3600,
    "d": 86400,
    "day": 86400,
}


@dataclass(frozen=True)
class RateLimitConfig:
    rate: int = 60
    period: int = 60
    scope: str = "default"

    @classmethod
    def parse(cls, rate: str, *, scope: str = "default") -> "RateLimitConfig":
        count, separator, unit = rate.partition("/")

        if not separator or unit not in _PERIOD_UNITS or not count.isdigit():
            raise ValueError(
                f"Invalid rate format: {rate!r}. Expected '<count>/<unit>' e.g. '10/min'."
            )

        return cls(rate=int(count), period=_PERIOD_UNITS[unit], scope=scope)

    def with_(self, **changes) -> "RateLimitConfig":
        return replace(self, **changes)


def _get_client_identifier(request: Request) -> str:
    user = getattr(request, "user", None)

    if user is not None and user.is_authenticated:
        return f"user-{getattr(user, 'user_id', user.pk)}"

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return f"ip-{forwarded_for.split(',')[0].strip()}"

    return f"ip-{request.META.get('REMOTE_ADDR', 'unknown')}"


def check_rate_limit(request: Request, config: RateLimitConfig) -> None:
    """
    Uses default LocMemCache to keep count its per-process,
    so count could be inaccurate when running multiple workers.
    Maybe switch to Redis/Database cache.
    """
    cache_key = f"ratelimit:{config.scope}:{_get_client_identifier(request)}"

    cache.add(cache_key, 0, timeout=config.period)

    try:
        request_count = cache.incr(cache_key)
    except ValueError:
        # Key expired between add and incr; restart the window.
        cache.add(cache_key, 1, timeout=config.period)
        request_count = 1

    if request_count > config.rate:
        try:
            ttl = cache.ttl(cache_key)
        except (AttributeError, NotImplementedError):
            # Not every backend exposes ttl() (e.g. Django's built-in LocMemCache);
            # fall back to the full configured period as the retry hint.
            ttl = None

        raise Throttled(wait=ttl if ttl and ttl > 0 else config.period)
