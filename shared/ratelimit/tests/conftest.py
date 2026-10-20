import pytest
from django.core.cache import cache
from django.http import HttpRequest
from rest_framework.request import Request


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """Isolate rate-limit counters: LocMemCache persists for the whole test process."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_request():
    """Build a DRF Request for unit-testing the rate-limit helpers without HTTP."""

    def _make_request(*, user=None, meta=None):
        http_request = HttpRequest()

        if meta is not None:
            http_request.META.update(meta)

        request = Request(http_request)

        if user is not None:
            request._user = user

        return request

    return _make_request
