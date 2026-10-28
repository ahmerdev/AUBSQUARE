from django.db import migrations

NEW_MODULES = ("invoices", "payments", "billing_reports", "billing_settings")


def add_modules(apps, schema_editor):
    """Give existing roles the billing permissions from the defaults (never removes or changes anything else)."""
    from apps.accounts.permissions import DEFAULT_ROLES

    Role = apps.get_model("accounts", "Role")
    for slug, spec in DEFAULT_ROLES.items():
        role = Role.objects.filter(slug=slug).first()
        if not role:
            continue
        perms = dict(role.permissions or {})
        changed = False
        for m in NEW_MODULES:
            if m not in perms and m in spec["permissions"]:
                perms[m] = spec["permissions"][m]
                changed = True
        if changed:
            role.permissions = perms
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_outbound_permissions")]
    operations = [migrations.RunPython(add_modules, migrations.RunPython.noop)]
