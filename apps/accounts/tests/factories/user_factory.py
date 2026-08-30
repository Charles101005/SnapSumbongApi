import factory
from django.contrib.auth.hashers import make_password

from apps.accounts.models import Users


TEST_PASSWORD = 'Password2005'

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Users

    class Params:
        _has_middle_name = factory.Faker('boolean', chance_of_getting_true=50)

    last_name = factory.Faker('last_name')
    first_name = factory.Faker('first_name')
    middle_name = factory.Maybe(
        '_has_middle_name',
        yes_declaration=factory.Faker('first_name'),
        no_declaration=None
    )

    email = factory.Sequence(lambda n: f'email{n}@email.com')
    password = factory.LazyFunction(lambda: make_password(TEST_PASSWORD))

    has_changed_password = True
