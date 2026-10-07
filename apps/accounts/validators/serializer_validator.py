from django.core.validators import RegexValidator

ten_digit_psgc_code_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='Invalid PSGC format code. Must be a valid 10-digit numeric character string.'
)