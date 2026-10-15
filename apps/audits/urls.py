from django.urls import path

from .views.audit_log_view import AuditLogListView, AuditLogDetailView
from .views.lookup_view import lookup_audit_log_modules_view


urlpatterns = [
    path("lookup/modules/", lookup_audit_log_modules_view, name="lookup_audit_log_modules"),

    path("", AuditLogListView.as_view(), name="audit_log_list"),
    path("<str:audit_log_number>/", AuditLogDetailView.as_view(), name="audit_log_detail"),
]