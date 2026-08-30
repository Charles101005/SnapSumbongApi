import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import VerificationRequest


TEST_OTP = "2005"

class VerificationRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VerificationRequest

    email = factory.Sequence(lambda n: f'verification{n}@email.com')

    otp_hash = factory.LazyFunction(lambda: make_password(TEST_OTP))

    expires_at = factory.LazyFunction(
        lambda: timezone.now() + settings.VERIFICATION_REQUEST_CONFIG['VERIFICATION_REQUEST_LIFETIME']
    )

    last_sent_at = factory.LazyFunction(timezone.now)


