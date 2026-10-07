import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class TraditionalPasswordComplexityValidator:
    def validate(self, password, user=None):
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("The password must contain at least one lowercase letter."),
                code='PASSWORD_NO_LOWER',
            )

        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter."),
                code='PASSWORD_NO_UPPER',
            )

        if not re.search(r"[0-9]", password):
            raise ValidationError(
                _("The password must contain at least one number."),
                code='PASSWORD_NO_NUMBER',
            )

        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError(
                _("The password must contain at least one special character."),
                code='PASSWORD_NO_SPECIAL_CHAR',
            )

