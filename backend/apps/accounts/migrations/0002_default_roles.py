from django.db import migrations

from apps.accounts.permissions import DEFAULT_ROLES


def create_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for slug, spec in DEFAULT_ROLES.items():
        Role.objects.update_or_create(
            slug=slug, defaults={"name": spec["name"], "description": spec["description"], "permissions": spec["permissions"], "is_system": True}
        ) if not Role.objects.filter(slug=slug).exists() else None


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(create_roles, migrations.RunPython.noop)]
