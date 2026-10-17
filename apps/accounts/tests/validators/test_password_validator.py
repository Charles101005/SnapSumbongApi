import pytest
from django.core.exceptions import ValidationError

from apps.accounts.validators.password_validator import TraditionalPasswordComplexityValidator


validator = TraditionalPasswordComplexityValidator()


@pytest.mark.parametrize(
    'password',
    [
        'ABCD123!',   # missing lowercase
        'abcd123!',   # missing uppercase
        'abcdABCD!',  # missing number
        'abcdABCD1',  # missing special character
    ],
)
def test_password_missing_required_character_class_is_rejected(password):
    with pytest.raises(ValidationError):
        validator.validate(password)


def test_password_with_all_character_classes_is_accepted():
    validator.validate('abcdABCD1!')
