import factory

from apps.accounts.models import Roles


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Roles
        skip_postgeneration_save = True

    role_name = factory.Sequence(lambda n: f"Test Role {n}")
    role_code = factory.LazyAttribute(lambda obj: Roles.format_role_code(obj.role_name))
    description = "Test role description"
    is_protected = False
    is_active = True

    @factory.post_generation
    def permissions(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.permissions.set(extracted)
