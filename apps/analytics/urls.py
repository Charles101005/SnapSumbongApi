from django.urls import path

from .views.analytic_view import (
    hazard_report_metrics_view,
    employee_metrics_view,
    citizen_metrics_view,
    handler_compliance_view,
)


urlpatterns = [
    path("hazard-report/", hazard_report_metrics_view, name="hazard_report_metrics"),
    path("compliance/", handler_compliance_view, name="handler_compliance"),

    path("employee/<str:user_number>/", employee_metrics_view, name="employee_metrics"),
    path("citizen/<str:user_number>/", citizen_metrics_view, name="citizen_metrics"),
]