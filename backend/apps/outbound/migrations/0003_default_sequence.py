from django.db import migrations


def create_default(apps, schema_editor):
    """One ready-to-use sequence (first email, follow-ups on day 3 and 7). Steps auto-write from the real audit; every draft still needs approval."""
    Sequence = apps.get_model("outbound", "Sequence")
    Step = apps.get_model("outbound", "SequenceStep")
    if Sequence.objects.exists():
        return
    seq = Sequence.objects.create(name="Standard 3-step follow-up", description="First email, then gentle follow-ups after 3 and 7 days. Stops when the prospect replies.", is_active=True)
    for order, delay in ((1, 0), (2, 3), (3, 4)):
        Step.objects.create(sequence=seq, order=order, delay_days=delay)


class Migration(migrations.Migration):
    dependencies = [("outbound", "0002_outreachmessage_queued_at")]
    operations = [migrations.RunPython(create_default, migrations.RunPython.noop)]
