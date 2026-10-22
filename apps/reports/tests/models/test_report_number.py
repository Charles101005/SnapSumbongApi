import pytest

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestReportNumberAssignment:
    def test_collision_regenerates_the_number(self, mocker):
        taken = HazardReportFactory()

        generator = mocker.patch(
            "apps.reports.models.hazard_report_model.model_number_generator",
            side_effect=[taken.report_number, "REPT-20240101-FRESH1"],
        )
        report = HazardReportFactory()

        assert generator.call_count == 2
        assert report.report_number == "REPT-20240101-FRESH1"
        assert HazardReports.objects.filter(
            report_number="REPT-20240101-FRESH1"
        ).exists()

    def test_a_provided_number_is_preserved(self):
        report = HazardReportFactory(report_number="REPT-20240101-PRESET")
        report.save()

        assert report.report_number == "REPT-20240101-PRESET"
