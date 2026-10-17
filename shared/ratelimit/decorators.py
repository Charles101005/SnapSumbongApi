from functools import wraps
from typing import Any, Callable

from rest_framework.request import Request

from .base_ratelimit import RateLimitConfig, check_rate_limit


def _get_request_from_args(args: tuple[Any, ...]) -> Request:
    if args and hasattr(args[0], 'user'):
        return args[0]

    if len(args) > 1 and hasattr(args[1], 'user'):
        return args[1]

    raise ValueError("Missing required 'request' argument")


def _resolve_config(
        config: RateLimitConfig|type[RateLimitConfig]|None,
        rate: str|int|None,
        period: int|None,
        scope: str,
) -> RateLimitConfig:
    if config is not None:
        if isinstance(config, type):
            config = config()

        overrides = {
            key: value
            for key, value in {"rate": rate, "period": period, "scope": scope}.items()
            if value is not None
        }

        return config.with_(**overrides) if overrides else config.with_(scope=scope)

    if rate is None:
        raise ValueError("Requires either a config or a rate")

    if isinstance(rate, str):
        resolved = RateLimitConfig.parse(rate, scope=scope)

        if period is not None:
            resolved = resolved.with_(period=period)

        return resolved

    return RateLimitConfig(rate=rate, period=period or 60, scope=scope)


def rate_limit(
        config: RateLimitConfig|type[RateLimitConfig]|None = None,
        *,
        rate: str|int|None = None,
        period: int|None = None,
        scope: str|None = None,
):
    """
    By default each decorated endpoint gets its own bucket
    Place it outermost so throttled requests are rejected early.
    """
    def decorator(func: Callable) -> Callable:
        resolved = _resolve_config(
            config,
            rate=rate,
            period=period,
            scope=scope or f"{func.__module__}.{getattr(func, '__qualname__', func.__name__)}",
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            request = _get_request_from_args(args)
            check_rate_limit(request, resolved)

            return func(*args, **kwargs)

        return wrapper

    return decorator
