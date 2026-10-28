from django.db import migrations

from apps.leads.categories import lead_category


def backfill(apps, schema_editor):
    """Existing leads: use the earlier 'last contacted' time as the first reply, and group them by kind of work."""
    Lead = apps.get_model("leads", "Lead")
    for lead in Lead.objects.all().iterator():
        changed = []
        if lead.first_response_at is None:
            if lead.last_contacted_at:
                lead.first_response_at = lead.last_contacted_at
                changed.append("first_response_at")
            elif lead.status not in ("new",):
                lead.first_response_at = lead.updated_at
                changed.append("first_response_at")
        if lead.category == "other":
            cat = lead_category(lead.message[:400], lead.service_label)
            if cat != "other":
                lead.category = cat
                changed.append("category")
        if changed:
            lead.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("leads", "0002_lead_category_lead_first_response_at_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
