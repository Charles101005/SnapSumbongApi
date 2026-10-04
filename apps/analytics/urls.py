from django.urls import path

from .views.analytic_view import (
    hazard_report_metrics_view,
    employee_metrics_view,
    citizen_metrics_view
)


urlpatterns = [
    path("hazard-report/", hazard_report_metrics_view, name="hazard_report_metrics"),

    path("employee/<str:user_number>/", employee_metrics_view, name="employee_metrics"),
    path("citizen/<str:user_number>/", citizen_metrics_view, name="citizen_metrics"),
]