from django.urls import path

from .views.report_view import ReportImageSignatureView, ReportListView, ReportDetailView, report_history_detail_view
from .views.hazard_category_view import HazardCategoryListView
from .views.lookup_view import lookup_filter_citizen_report_view


urlpatterns = [
    path('image-signature/', ReportImageSignatureView.as_view(), name='report_image_signature'),

    path('hazard-category/', HazardCategoryListView.as_view(), name='hazard_category_list'),

    path('lookup/', lookup_filter_citizen_report_view, name='lookup_citizen_report_view'),

    path('history/<str:report_number>/', report_history_detail_view, name='report_history'),
    path('', ReportListView.as_view(), name='report_list'),
    path('<str:report_number>/', ReportDetailView.as_view(), name='report_detail'),

]
