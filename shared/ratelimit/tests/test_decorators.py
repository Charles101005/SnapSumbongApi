import types

import pytest
from django.core.cache import cache
from rest_framework.exceptions import Throttled

from shared.ratelimit.base_ratelimit import RateLimitConfig
from shared.ratelimit.decorators import (
    _get_request_from_args,
    _resolve_config,
    rate_limit,
)
from shared.ratelimit.ratelimit import StrictRateLimit


class TestGetRequestFromArgs:
    def test_returns_first_arg_when_it_has_user(self, make_request):
        request = make_request()

        assert _get_request_from_args((request,)) is request

    def test_returns_second_arg_when_first_lacks_user(self, make_request):
        # Class-based view methods receive (self, request); self has no .user
        view_instance = types.SimpleNamespace()
        request = make_request()

        assert _get_request_from_args((view_instance, request)) is request

    def test_prefers_first_arg_when_both_have_user(self, make_request):
        first, second = make_request(), make_request()

        assert _get_request_from_args((first, second)) is first

    @pytest.mark.parametrize("args", [(), (types.SimpleNamespace(),)])
    def test_raises_when_no_request_found(self, args):
        with pytest.raises(ValueError, match="Missing required 'request' argument"):
            _get_request_from_args(args)


class TestResolveConfig:
    def test_config_instance_gets_scope_applied(self):
        config = StrictRateLimit()

        resolved = _resolve_config(config, rate=None, period=None, scope="custom")

        assert isinstance(resolved, StrictRateLimit)
        assert resolved.scope == "custom"
        assert resolved.rate == 10

    def test_config_class_is_instantiated(self):
        resolved = _resolve_config(StrictRateLimit, rate=None, period=None, scope="custom")

        assert isinstance(resolved, StrictRateLimit)
        assert resolved.rate == 10
        assert resolved.scope == "custom"

    def test_overrides_replace_config_values(self):
        resolved = _resolve_config(
            StrictRateLimit(), rate=5, period=30, scope="custom"
        )

        assert (resolved.rate, resolved.period, resolved.scope) == (5, 30, "custom")

    def test_string_rate_is_parsed(self):
        resolved = _resolve_config(None, rate="10/min", period=None, scope="custom")

        assert resolved == RateLimitConfig(rate=10, period=60, scope="custom")

    def test_string_rate_period_override(self):
        resolved = _resolve_config(None, rate="10/min", period=30, scope="custom")

        assert resolved.period == 30

    def test_int_rate_defaults_period_to_sixty(self):
        resolved = _resolve_config(None, rate=10, period=None, scope="custom")

        assert resolved == RateLimitConfig(rate=10, period=60, scope="custom")

    def test_int_rate_with_explicit_period(self):
        resolved = _resolve_config(None, rate=10, period=30, scope="custom")

        assert resolved == RateLimitConfig(rate=10, period=30, scope="custom")

    def test_missing_config_and_rate_raises(self):
        with pytest.raises(ValueError, match="Requires either a config or a rate"):
            _resolve_config(None, rate=None, period=None, scope="custom")


class TestRateLimitDecorator:
    def test_preserves_function_metadata(self):
        @rate_limit(rate="10/min", scope="decorator-meta")
        def endpoint(request):
            """Endpoint docstring."""

            return "ok"

        assert endpoint.__name__ == "endpoint"
        assert endpoint.__doc__ == "Endpoint docstring."

    def test_default_scope_is_module_and_qualname(self, mocker, make_request):
        check = mocker.patch("shared.ratelimit.decorators.check_rate_limit")

        @rate_limit(rate="10/min")
        def endpoint(request):
            return "ok"

        request = make_request()
        assert endpoint(request) == "ok"

        resolved_config = check.call_args.args[1]
        assert resolved_config.scope == f"{endpoint.__module__}.{endpoint.__qualname__}"

    def test_config_class_argument_resolved(self, mocker, make_request):
        check = mocker.patch("shared.ratelimit.decorators.check_rate_limit")

        @rate_limit(StrictRateLimit, scope="decorator-class")
        def endpoint(request):
            return "ok"

        request = make_request()
        endpoint(request)

        check.assert_called_once()
        assert check.call_args.args[0] is request
        config = check.call_args.args[1]
        assert isinstance(config, StrictRateLimit)
        assert (config.rate, config.period, config.scope) == (10, 60, "decorator-class")

    def test_check_runs_before_view_body(self, make_request):
        # Real check_rate_limit must pass (within limit) for the body to run.
        @rate_limit(rate="2/min", scope="decorator-order")
        def endpoint(request):
            return cache.get("ratelimit:decorator-order:ip-1.1.1.1")

        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})

        assert endpoint(request) == 1

    def test_within_limit_calls_through(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})

        @rate_limit(rate="2/min", scope="decorator-within")
        def endpoint(request):
            return "ok"

        assert [endpoint(request) for _ in range(2)] == ["ok", "ok"]
        assert cache.get("ratelimit:decorator-within:ip-1.1.1.1") == 2

    def test_throttled_propagates_to_caller(self, mocker, make_request):
        mock_cache = mocker.patch("shared.ratelimit.base_ratelimit.cache")
        mock_cache.incr.return_value = 99
        mock_cache.ttl.return_value = 25

        @rate_limit(rate=2, period=60, scope="decorator-throttle")
        def endpoint(request):
            return "ok"

        with pytest.raises(Throttled) as exc_info:
            endpoint(make_request(meta={"REMOTE_ADDR": "1.1.1.1"}))

        assert exc_info.value.wait == 25

    def test_call_without_arguments_raises_value_error(self):
        @rate_limit(rate="10/min", scope="decorator-no-request")
        def endpoint(request):
            return "ok"

        with pytest.raises(ValueError, match="Missing required 'request' argument"):
            endpoint()

    def test_call_with_non_request_arg_raises_value_error(self):
        @rate_limit(rate="10/min", scope="decorator-no-request")
        def endpoint(request):
            return "ok"

        with pytest.raises(ValueError, match="Missing required 'request' argument"):
            endpoint(types.SimpleNamespace())
