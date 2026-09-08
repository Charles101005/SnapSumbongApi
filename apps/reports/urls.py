from django.urls import path

from .views.report_view import ReportImageSignatureView, ReportListView, ReportDetailView
from .views.hazard_category_view import HazardCategoryListView


urlpatterns = [
    path('image-signature/', ReportImageSignatureView.as_view(), name='report_image_signature'),

    path('hazard-category/', HazardCategoryListView.as_view(), name='hazard_category_list'),

    path('', ReportListView.as_view(), name='report_list'),
    path('<str:report_number>/', ReportDetailView.as_view(), name='report_detail'),

]
