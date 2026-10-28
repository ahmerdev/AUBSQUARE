"""Keep old URLs working: when a published item's slug changes, create a 301 to the new URL."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

PREFIX = {"Service": "/services/", "Project": "/portfolio/", "CaseStudy": "/case-studies/", "Post": "/blog/"}


def _watched(sender):
    return sender.__name__ in PREFIX and sender._meta.app_label in ("cms", "blog")


@receiver(pre_save, dispatch_uid="aub_slug_remember")
def remember_slug(sender, instance, raw=False, **kwargs):
    if raw or not _watched(sender) or not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).values_list("slug", flat=True).first()
    instance._old_slug = old


@receiver(post_save, dispatch_uid="aub_slug_redirect")
def create_redirect(sender, instance, created=False, raw=False, **kwargs):
    if raw or created or not _watched(sender):
        return
    old = getattr(instance, "_old_slug", None)
    if not old or old == instance.slug:
        return
    from .models import Redirect

    prefix = PREFIX[sender.__name__]
    new_path = f"{prefix}{instance.slug}"
    # Anything that pointed at the old path now points straight at the new one (no chains).
    Redirect.objects.filter(to_path=f"{prefix}{old}").update(to_path=new_path)
    # If we're moving back to a slug that had a redirect, remove that redirect (it would loop).
    Redirect.objects.filter(from_path=new_path, auto_created=True).delete()
    Redirect.objects.update_or_create(
        from_path=f"{prefix}{old}",
        defaults={"to_path": new_path, "permanent": True, "is_active": True, "auto_created": True, "note": f"Slug changed on “{str(instance)[:80]}”"},
    )
    instance._old_slug = None
