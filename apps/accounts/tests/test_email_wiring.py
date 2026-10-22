import pytest
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Users, VerificationRequest, CitizenWarnings
from apps.accounts.services import (
    VerificationService, UserService, ModerationService, ForgotPasswordService,
)
from apps.reports.models import HazardReports, HazardCategories
from apps.reports.services import ReportService
from external.email.email_service import EmailService


@pytest.mark.django_db
class TestEmailWiringEndToEnd:
    """Only ResendClient.deliver (the network boundary) is stubbed, so every
    template renders with the real context each service builds."""

    @pytest.fixture(autouse=True)
    def capture(self, mocker):
        self.sent = []
        mocker.patch.object(
            EmailService._client, 'deliver',
            side_effect=lambda **kw: self.sent.append(kw) or True,
        )
        return self

    def emails(self):
        return self.sent

    def test_registration_otp(self, citizen_role, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            VerificationService.create(
                email='reg@x.com',
                purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
                payload={'first_name': 'Juan', 'last_name': 'Dela Cruz'},
            )

        (msg,) = self.emails()
        assert msg['subject'] == 'Your SnapSumbong registration code'
        assert 'Hi Juan,' in msg['html_body']
        assert 'Your Registration code: ' in msg['html_body']

    def test_forgot_password_otp_uses_existing_user_name(self, citizen_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        UserFactory(role=citizen_role, email='fp@x.com', first_name='Maria')

        with django_capture_on_commit_callbacks(execute=True):
            ForgotPasswordService.request_reset_password('fp@x.com')

        (msg,) = self.emails()
        assert msg['subject'] == 'Your SnapSumbong password reset code'
        assert 'Hi Maria,' in msg['html_body']

    def test_employee_temp_password(self, system_admin_role, mocker, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        actor = UserFactory(role=system_admin_role)

        with django_capture_on_commit_callbacks(execute=True):
            result = UserService.create_staff(
                actor=actor, email='emp@x.com', role_id=system_admin_role.role_id,
                last_name='Santos', first_name='Ana', contact_number='0917',
                birth_date=timezone.now().date(), gender='F', street_address='1 Main',
                region_code='01', province_code='01', city_code='01', barangay_code='01',
            )

        staff = result.value
        (msg,) = self.emails()
        assert msg['subject'] == 'Your SnapSumbong staff account has been created'
        assert staff.user_number in msg['html_body']
        assert 'Ana' in msg['html_body']

    def test_self_deactivation(self, citizen_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        user = UserFactory(role=citizen_role, email='deac@x.com', first_name='Ben')

        with django_capture_on_commit_callbacks(execute=True):
            UserService.deactivate_account(user)

        (msg,) = self.emails()
        assert msg['subject'] == 'Your SnapSumbong account has been deactivated'
        assert 'Hi Ben,' in msg['html_body']
        assert 'deac@x.com' in msg['html_body']

    def test_deactivation_noop_when_already_inactive(self, citizen_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        user = UserFactory(role=citizen_role)
        user.is_active = False
        user.save(update_fields=['is_active'])

        with django_capture_on_commit_callbacks(execute=True):
            UserService.deactivate_account(user)

        assert self.emails() == []

    def test_report_submission_and_status_update(self, citizen_role, supervisor_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        citizen = UserFactory(role=citizen_role, email='rep@x.com', first_name='Lia')
        staff = UserFactory(role=supervisor_role, is_staff=True)

        category = HazardCategories.objects.create(
            hazard_name=f'Test Hazard {timezone.now().timestamp()}',
            response_time_days=3,
        )

        with django_capture_on_commit_callbacks(execute=True):
            created = ReportService.create_assign_hazard_report(
                reported_by_id=citizen.user_id, category_id=category.hazard_id,
                latitude=Decimal('14.5995'), longitude=Decimal('120.9842'),
                address='123 Rizal St', description='Deep pothole',
                is_anonymous=False, image_urls=['https://cdn/x.jpg'],
            )

        report = created.value
        assert len(self.emails()) == 1
        assert self.emails()[0]['subject'] == f'We received your report {report.report_number}'
        assert '123 Rizal St' in self.emails()[0]['html_body']

        with django_capture_on_commit_callbacks(execute=True):
            ReportService.update_authorized_assigned_report(
                user=staff, report_number=report.report_number,
                new_status_str='UNDER_REVIEW', remarks='Triaged by desk.',
            )

        assert len(self.emails()) == 2
        status_msg = self.emails()[1]
        assert report.report_number in status_msg['subject']
        assert 'Triaged by desk.' in status_msg['html_body']
        assert 'Under Review' in status_msg['html_body']

    def test_status_update_without_remarks_hides_block(self, citizen_role, supervisor_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        citizen = UserFactory(role=citizen_role)
        staff = UserFactory(role=supervisor_role, is_staff=True)
        category = HazardCategories.objects.create(
            hazard_name=f'Quiet Cat {timezone.now().timestamp()}', response_time_days=3
        )

        with django_capture_on_commit_callbacks(execute=True):
            report = ReportService.create_assign_hazard_report(
                reported_by_id=citizen.user_id, category_id=category.hazard_id,
                latitude=Decimal('14.5'), longitude=Decimal('120.9'),
                address='A', description='B', is_anonymous=False, image_urls=[],
            ).value

        with django_capture_on_commit_callbacks(execute=True):
            ReportService.update_authorized_assigned_report(
                user=staff, report_number=report.report_number,
                new_status_str='UNDER_REVIEW',
            )

        assert len(self.emails()) == 2
        msg = self.emails()[1]
        assert 'Remarks' not in msg['html_body']

    def test_ban_email(self, citizen_role, supervisor_role, django_capture_on_commit_callbacks):
        from apps.accounts.tests.factories import UserFactory
        citizen = UserFactory(role=citizen_role, email='banned@x.com', first_name='Rey')
        actor = UserFactory(role=supervisor_role, is_staff=True)

        category = HazardCategories.objects.create(
            hazard_name=f'Ban Cat {timezone.now().timestamp()}', response_time_days=3
        )
        # 3 warnings is BAN_WARNING_THRESHOLD -- the count path (no
        # report_number arg) taken here.
        for i in range(3):
            report = HazardReports.objects.create(
                reported_by=citizen, category=category,
                latitude=Decimal('14.5'), longitude=Decimal('120.9'),
                address=f'Addr {i}', description='spam',
            )
            CitizenWarnings.objects.create(user=citizen, warned_by=actor, reason='spam', report=report)
        HazardReports.objects.create(
            reported_by=citizen, category=category,
            latitude=Decimal('14.5'), longitude=Decimal('120.9'),
            address='clean', description='legit',
        )

        with django_capture_on_commit_callbacks(execute=True):
            ModerationService.ban_citizen(actor=actor, user_number=citizen.user_number, reason='Spam reports')

        (msg,) = self.emails()
        assert msg['subject'] == 'Your SnapSumbong account has been banned'
        assert '3 of 4 submitted' in msg['html_body']
        assert 'banned@x.com' in msg['html_body']
        assert 'Spam reports' in msg['html_body']
        # case_id came through as the ban audit log number
        assert msg['to_emails'] == ['banned@x.com']
