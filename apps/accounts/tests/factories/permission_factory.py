import factory

from apps.accounts.models import Permissions


class PermissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Permissions

    permission_name = factory.Sequence(lambda n: f"perm:module_{n}_action")
    description = factory.Faker("sentence", nb_words=6)
    module = factory.Sequence(lambda n: f"module_{n}")
