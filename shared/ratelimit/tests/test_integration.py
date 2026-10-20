import pytest
from django.core.cache import cache
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.tests.factories.user_factory import UserFactory
from shared.ratelimit.decorators import rate_limit


@api_view(['GET'])
@permission_classes([AllowAny])
@rate_limit(rate='2/min', scope='itest-basic')
def basic_view(request):
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([AllowAny])
@rate_limit(rate='1/min', scope='itest-other')
def other_scope_view(request):
    return Response({'ok': True})


urlpatterns = [
    path('ratelimit-test/basic/', basic_view),
    path('ratelimit-test/other/', other_scope_view),
]

pytestmark = pytest.mark.urls(__name__)

BASIC_URL = '/ratelimit-test/basic/'
OTHER_URL = '/ratelimit-test/other/'


def test_allows_requests_within_limit(api_client):
    first = api_client.get(BASIC_URL)
    second = api_client.get(BASIC_URL)

    assert first.status_code == 200
    assert second.status_code == 200


def test_returns_429_after_exceeding_limit(api_client):
    api_client.get(BASIC_URL)
    api_client.get(BASIC_URL)

    response = api_client.get(BASIC_URL)

    assert response.status_code == 429


@pytest.mark.django_db
def test_authenticated_and_anonymous_have_separate_buckets(api_client):
    user = UserFactory()

    api_client.force_authenticate(user=user)
    assert api_client.get(OTHER_URL).status_code == 200

    # Same client, now anonymous: would exceed the 1/min rate if buckets were shared
    api_client.force_authenticate(user=None)
    assert api_client.get(OTHER_URL).status_code == 200

    assert cache.get(f"ratelimit:itest-other:user-{user.user_id}") == 1
    assert cache.get("ratelimit:itest-other:ip-127.0.0.1") == 1


def test_different_scopes_are_isolated(api_client):
    # basic is 2/min, other is 1/min: a shared bucket would throttle the second call
    assert api_client.get(BASIC_URL).status_code == 200
    assert api_client.get(OTHER_URL).status_code == 200


def test_x_forwarded_for_is_used_as_identifier(api_client):
    first = api_client.get(BASIC_URL, HTTP_X_FORWARDED_FOR='10.9.9.9')
    second = api_client.get(BASIC_URL, HTTP_X_FORWARDED_FOR='10.8.8.8')

    assert first.status_code == 200
    assert second.status_code == 200

    assert cache.get("ratelimit:itest-basic:ip-10.9.9.9") == 1
    assert cache.get("ratelimit:itest-basic:ip-10.8.8.8") == 1


def test_remote_addr_is_used_without_forwarded_for(api_client):
    response = api_client.get(BASIC_URL)

    assert response.status_code == 200

    assert cache.get("ratelimit:itest-basic:ip-127.0.0.1") == 1
