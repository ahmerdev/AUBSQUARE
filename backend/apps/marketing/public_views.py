from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache

from .models import Subscriber


@never_cache
@csrf_protect
def unsubscribe(request, token):
    sub = Subscriber.objects.filter(token=token).first()
    if not sub:
        raise Http404
    done = sub.status == "unsubscribed"
    if request.method == "POST":
        if sub.status != "unsubscribed":
            sub.status, sub.unsubscribed_at = "unsubscribed", timezone.now()
            sub.save(update_fields=["status", "unsubscribed_at", "updated_at"])
        done = True
    return render(request, "public/unsubscribe.html", {"subscriber": sub, "done": done})
