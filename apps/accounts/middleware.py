from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.utils import timezone


class UpdateLastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if hasattr(request, 'user') and request.user.is_authenticated:
            now = timezone.now()
            last_active = getattr(request.user, 'last_active', None)

            if not last_active or (now - last_active) > timedelta(minutes=5):
                type(request.user).objects.filter(pk=request.user.pk).update(last_active=now)

        return response
