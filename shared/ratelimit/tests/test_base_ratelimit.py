import types

import pytest
from django.core.cache import cache
from rest_framework.exceptions import Throttled

from shared.ratelimit.base_ratelimit import (
    RateLimitConfig,
    _get_client_identifier,
    check_rate_limit,
)


class TestRateLimitConfigParse:
    @pytest.mark.parametrize(
        "rate,expected_rate,expected_period",
        [
            ("10/s", 10, 1),
            ("10/sec", 10, 1),
            ("10/second", 10, 1),
            ("10/m", 10, 60),
            ("10/min", 10, 60),
            ("10/minute", 10, 60),
            ("10/h", 10, 3600),
            ("10/hour", 10, 3600),
            ("10/d", 10, 86400),
            ("10/day", 10, 86400),
        ],
    )
    def test_parse_valid_rate_formats(self, rate, expected_rate, expected_period):
        config = RateLimitConfig.parse(rate, scope="unit-scope")

        assert config.rate == expected_rate
        assert config.period == expected_period
        assert config.scope == "unit-scope"

    def test_parse_uses_default_scope(self):
        config = RateLimitConfig.parse("5/min")

        assert config.scope == "default"

    @pytest.mark.parametrize(
        "rate",
        [
            "10",        # no separator
            "min",       # no separator, only unit
            "/min",      # empty count
            "abc/min",   # non-digit count
            "10/xyz",    # unknown unit
            "10//",      # garbage unit
        ],
    )
    def test_parse_invalid_rate_formats_raise(self, rate):
        with pytest.raises(ValueError, match="Invalid rate format"):
            RateLimitConfig.parse(rate)


class TestRateLimitConfigWith:
    def test_with_returns_new_config_with_changes(self):
        config = RateLimitConfig(rate=60, period=60, scope="a")

        updated = config.with_(rate=5, scope="b")

        assert updated.rate == 5
        assert updated.scope == "b"
        assert updated.period == 60
        # original is untouched (frozen dataclass semantics)
        assert config.rate == 60
        assert config.scope == "a"


class TestGetClientIdentifier:
    def test_authenticated_user_uses_user_id(self, make_request):
        user = types.SimpleNamespace(is_authenticated=True, user_id=42, pk=99)

        request = make_request(user=user, meta={"REMOTE_ADDR": "1.2.3.4"})

        assert _get_client_identifier(request) == "user-42"

    def test_authenticated_user_falls_back_to_pk(self, make_request):
        user = types.SimpleNamespace(is_authenticated=True, pk=7)

        request = make_request(user=user, meta={"REMOTE_ADDR": "1.2.3.4"})

        assert _get_client_identifier(request) == "user-7"

    def test_anonymous_user_uses_forwarded_for_first_ip(self, make_request):
        request = make_request(
            meta={
                "HTTP_X_FORWARDED_FOR": "9.9.9.9, 8.8.8.8",
                "REMOTE_ADDR": "1.2.3.4",
            }
        )

        assert _get_client_identifier(request) == "ip-9.9.9.9"

    def test_forwarded_for_strips_whitespace(self, make_request):
        request = make_request(meta={"HTTP_X_FORWARDED_FOR": " 10.0.0.1 , 10.0.0.2"})

        assert _get_client_identifier(request) == "ip-10.0.0.1"

    def test_anonymous_user_uses_remote_addr(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.2.3.4"})

        assert _get_client_identifier(request) == "ip-1.2.3.4"

    def test_missing_remote_addr_defaults_to_unknown(self, make_request):
        request = make_request(meta={})

        assert _get_client_identifier(request) == "ip-unknown"

    def test_unauthenticated_user_with_user_attr_falls_through_to_ip(self, make_request):
        user = types.SimpleNamespace(is_authenticated=False, user_id=42)

        request = make_request(user=user, meta={"REMOTE_ADDR": "1.2.3.4"})

        assert _get_client_identifier(request) == "ip-1.2.3.4"


class TestCheckRateLimit:
    def _config(self, **overrides):
        base = {"rate": 3, "period": 60, "scope": "unit-check"}
        base.update(overrides)
        return RateLimitConfig(**base)

    def test_first_request_starts_window_at_one(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config()

        check_rate_limit(request, config)

        assert cache.get("ratelimit:unit-check:ip-1.1.1.1") == 1

    def test_requests_within_limit_are_allowed(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config(rate=3)

        for _ in range(3):
            check_rate_limit(request, config)  # must not raise

        assert cache.get("ratelimit:unit-check:ip-1.1.1.1") == 3

    def test_request_over_limit_raises_throttled(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config(rate=2)

        check_rate_limit(request, config)
        check_rate_limit(request, config)

        with pytest.raises(Throttled) as exc_info:
            check_rate_limit(request, config)

        assert 0 < exc_info.value.wait <= 60

    def test_throttled_wait_uses_cache_ttl_when_available(self, mocker, make_request):
        # Throttled(wait=...) should carry the remaining window from cache.ttl()
        # (ceil'd by DRF). Mock the whole cache entry to control both incr and ttl.
        mock_cache = mocker.patch("shared.ratelimit.base_ratelimit.cache")
        mock_cache.incr.return_value = 4  # over the rate below
        mock_cache.ttl.return_value = 12.5
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config(rate=3, period=45)

        with pytest.raises(Throttled) as exc_info:
            check_rate_limit(request, config)

        assert exc_info.value.wait == 13  # math.ceil(12.5)

    def test_throttled_wait_falls_back_to_period_when_ttl_unavailable(self, mocker, make_request):
        # Falsy ttl (None/0/negative) must fall back to the configured period.
        mock_cache = mocker.patch("shared.ratelimit.base_ratelimit.cache")
        mock_cache.incr.return_value = 4
        mock_cache.ttl.return_value = None
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config(rate=3, period=45)

        with pytest.raises(Throttled) as exc_info:
            check_rate_limit(request, config)

        assert exc_info.value.wait == 45

    def test_expired_key_between_add_and_incr_restarts_window(self, mocker, make_request):
        # cache key vanishing between add() and incr() raises ValueError;
        # the window must restart at 1 instead of crashing.
        mock_cache = mocker.patch("shared.ratelimit.base_ratelimit.cache")
        mock_cache.incr.side_effect = ValueError("key expired")
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})
        config = self._config(rate=5, scope="unit-restart")

        check_rate_limit(request, config)  # must not raise

        mock_cache.add.assert_any_call("ratelimit:unit-restart:ip-1.1.1.1", 1, timeout=60)

    def test_different_scopes_use_separate_buckets(self, make_request):
        request = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})

        check_rate_limit(request, self._config(scope="scope-one"))
        check_rate_limit(request, self._config(scope="scope-two"))

        assert cache.get("ratelimit:scope-one:ip-1.1.1.1") == 1
        assert cache.get("ratelimit:scope-two:ip-1.1.1.1") == 1

    def test_different_identifiers_use_separate_buckets(self, make_request):
        config = self._config(rate=1)

        check_rate_limit(make_request(meta={"REMOTE_ADDR": "1.1.1.1"}), config)
        check_rate_limit(make_request(meta={"REMOTE_ADDR": "2.2.2.2"}), config)

        assert cache.get("ratelimit:unit-check:ip-1.1.1.1") == 1
        assert cache.get("ratelimit:unit-check:ip-2.2.2.2") == 1

    def test_authenticated_and_anonymous_buckets_are_isolated(self, make_request):
        config = self._config(rate=1)
        authenticated = make_request(
            user=types.SimpleNamespace(is_authenticated=True, user_id=1, pk=1),
            meta={"REMOTE_ADDR": "1.1.1.1"},
        )
        anonymous = make_request(meta={"REMOTE_ADDR": "1.1.1.1"})

        check_rate_limit(authenticated, config)
        check_rate_limit(anonymous, config)

        assert cache.get("ratelimit:unit-check:user-1") == 1
        assert cache.get("ratelimit:unit-check:ip-1.1.1.1") == 1
