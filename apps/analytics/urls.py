from django.urls import path

from .views.analytic_view import hazard_report_metrics_view


urlpatterns = [
    path("hazard-report/", hazard_report_metrics_view, name="hazard_report_metrics"),
]