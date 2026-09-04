from django.urls import path

from .views.report_view import ReportImageSignatureView, ReportListView, ReportDetailView


urlpatterns = [
    path('image-signature/', ReportImageSignatureView.as_view(), name='report_image_signature'),

    path('', ReportListView.as_view(), name='report_list'),
    path('<str:report_number>/', ReportDetailView.as_view(), name='report_detail'),
]
