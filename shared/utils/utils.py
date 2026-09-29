import secrets
import string

from django.utils import timezone

def model_number_generator(prefix: str, suffix_length: int=6) -> str:
    SUFFIX_CHOICES = string.digits + string.ascii_uppercase

    prefix = prefix.upper()
    date_str = timezone.now().strftime('%Y%m%d')
    suffix = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(suffix_length))

    return f"{prefix}-{date_str}-{suffix}"
