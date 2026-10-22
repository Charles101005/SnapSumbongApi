from django.urls import path

from .views.analytic_view import (
    hazard_report_metrics_view,
    handler_overview_view,
    employee_metrics_view,
    citizen_metrics_view,
    handler_workload_view,
)


urlpatterns = [
    path("hazard-report/", hazard_report_metrics_view, name="hazard_report_metrics"),
    path("overview/", handler_overview_view, name="handler_overview"),
    path("handlers/", handler_workload_view, name="handler_workload"),

    path("employee/<str:user_number>/", employee_metrics_view, name="employee_metrics"),
    path("citizen/<str:user_number>/", citizen_metrics_view, name="citizen_metrics"),
]