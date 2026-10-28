from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.sanitize import clean_plain
from apps.core.services import log_activity
from apps.leads.models import Lead
from apps.mailer.models import EmailSettings
from apps.mailer.service import queue_email
from apps.marketing import services as mk
from apps.marketing.models import AdCreative, AdGroup, AdIntegration, Campaign, CampaignMetric, CampaignNote, EmailCampaign, Subscriber
from .mixins import forbidden, needs


def _totals(qs):
    t = qs.aggregate(impressions=Sum("impressions"), clicks=Sum("clicks"), spend=Sum("spend"), conversions=Sum("conversions"))
    t = {k: (v or 0) for k, v in t.items()}
    t["ctr"] = round(t["clicks"] / t["impressions"] * 100, 2) if t["impressions"] else None
    t["cpc"] = round(Decimal(t["spend"]) / t["clicks"], 2) if t["clicks"] else None
    t["cpa"] = round(Decimal(t["spend"]) / t["conversions"], 2) if t["conversions"] else None
    return t


class MetricForm(forms.ModelForm):
    class Meta:
        model = CampaignMetric
        fields = ["date", "impressions", "clicks", "spend", "conversions", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for n, f in self.fields.items():
            f.widget.attrs.setdefault("class", "input")


@needs("campaigns", "view")
def campaign_detail(request, pk):
    c = get_object_or_404(Campaign.objects.select_related("owner", "approved_by"), pk=pk)
    leads = Lead.objects.filter(is_spam=False, utm_campaign=c.utm_campaign) if c.utm_campaign else Lead.objects.none()
    mform = MetricForm(initial={"date": timezone.localdate()})
    return render(request, "dashboard/campaign_detail.html", {
        "c": c, "metrics": c.metrics.all()[:30], "totals": _totals(c.metrics.all()), "notes": c.activity_notes.select_related("author")[:20], "mform": mform,
        "leads_count": leads.count(), "leads_won": leads.filter(status="won").count(), "leads": leads[:5],
        "can_edit": request.user.can("campaigns", "edit"), "can_approve": request.user.can("campaigns", "approve"), "can_delete": request.user.can("campaigns", "delete"),
        "page_title": c.name, "crumbs": [("Dashboard", "/dashboard/"), ("Campaigns", "/dashboard/campaigns/"), (c.name, "")],
    })


@needs("campaigns", "edit")
@require_POST
def campaign_action(request, pk):
    c = get_object_or_404(Campaign, pk=pk)
    act = request.POST.get("action")
    u = request.user
    if act == "metric":
        form = MetricForm(request.POST)
        if form.is_valid():
            m = form.save(commit=False)
            m.campaign, m.recorded_by, m.data_source = c, u, "manual"
            m.save()
            log_activity(u, "campaign.metric_added", c, f"{m.date}", request)
            messages.success(request, "Results saved (marked as manually entered).")
        else:
            messages.error(request, "Check the results form: " + "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    elif act == "note":
        body = clean_plain(request.POST.get("body", ""), 500)
        if body:
            CampaignNote.objects.create(campaign=c, author=u, body=body)
    elif act == "submit":
        if c.status == "draft":
            c.status = "pending_approval"
            c.save(update_fields=["status", "updated_at"])
            from apps.core.services import notify

            notify("campaign", f"Campaign awaiting approval: {c.name}", "", f"/dashboard/campaigns/{c.pk}/overview/", module="campaigns")
            messages.success(request, "Submitted for approval.")
    elif act in ("approve", "activate", "pause", "complete", "cancel", "reopen"):
        if act == "approve" and not u.can("campaigns", "approve"):
            return forbidden(request)
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Please confirm this change.")
            return redirect("dashboard:campaign_detail", pk=pk)
        if act == "activate" and c.status not in ("approved", "paused"):
            messages.error(request, "A campaign must be approved before it can be marked active.")
            return redirect("dashboard:campaign_detail", pk=pk)
        new = {"approve": "approved", "activate": "active", "pause": "paused", "complete": "completed", "cancel": "cancelled", "reopen": "draft"}[act]
        c.status = new
        if act == "approve":
            c.approved_by, c.approved_at = u, timezone.now()
        c.save()
        log_activity(u, f"campaign.{act}", c, new, request)
        messages.success(request, f"Campaign marked {new.replace('_', ' ')} in this dashboard." + ("" if not c.channel.endswith("_ads") else " Note: nothing was changed on the ad platform."))
    return redirect("dashboard:campaign_detail", pk=pk)


@needs("campaigns", "edit")
@require_POST
def metric_delete(request, pk):
    m = get_object_or_404(CampaignMetric, pk=pk)
    cid = m.campaign_id
    m.delete()
    messages.success(request, "Entry removed.")
    return redirect("dashboard:campaign_detail", pk=cid)


# ------------------------------------------------------------------ ads manager
@needs("ads", "view")
def ads_overview(request):
    ad_campaigns = Campaign.objects.filter(channel__in=["google_ads", "meta_ads"])
    integrations = []
    for key, label in AdIntegration.PROVIDERS:
        obj, _ = AdIntegration.objects.get_or_create(provider=key)
        integrations.append({"key": key, "label": label, "obj": obj})
    return render(request, "dashboard/ads.html", {
        "campaigns": ad_campaigns.order_by("-created_at")[:10], "totals": _totals(CampaignMetric.objects.filter(campaign__in=ad_campaigns)),
        "groups": AdGroup.objects.select_related("campaign").order_by("-created_at")[:8], "creatives_pending": AdCreative.objects.filter(approval_status="pending").select_related("ad_group__campaign"),
        "creatives_total": AdCreative.objects.count(), "groups_total": AdGroup.objects.count(), "integrations": integrations,
        "can_approve": request.user.can("ads", "approve"), "can_create": request.user.can("ads", "create"),
        "page_title": "Ads manager", "crumbs": [("Dashboard", "/dashboard/"), ("Ads manager", "")],
    })


@needs("ads", "approve")
@require_POST
def creative_action(request, pk):
    cr = get_object_or_404(AdCreative, pk=pk)
    act = request.POST.get("action")
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Please confirm this change.")
    elif act in ("approve", "reject"):
        cr.approval_status = "approved" if act == "approve" else "rejected"
        cr.approved_by, cr.approved_at = request.user, timezone.now()
        cr.save()
        log_activity(request.user, f"creative.{act}", cr, cr.headline[:80], request)
        messages.success(request, f"Creative {act}d in this dashboard. It has not been published to any ad platform.")
    return redirect(request.POST.get("next") or "dashboard:ads")


# ------------------------------------------------------------------ email campaigns
@needs("campaigns", "view")
def email_campaign_send(request, pk):
    ec = get_object_or_404(EmailCampaign, pk=pk)
    es = EmailSettings.load()
    aud = mk.audience().count()
    html, text = mk.render_for(ec, mk.audience().first() or Subscriber(email="preview@example.com", token="preview"))
    ctx = {"ec": ec, "audience": aud, "smtp_ready": es.smtp_configured, "preview_html": html, "can_send": request.user.can("campaigns", "approve"),
           "page_title": f"Send: {ec.name}", "crumbs": [("Dashboard", "/dashboard/"), ("Email campaigns", "/dashboard/email-campaigns/"), (ec.name, "")]}
    if request.method == "POST":
        if not request.user.can("campaigns", "approve"):
            return forbidden(request)
        act = request.POST.get("action")
        if act == "test":
            to = request.user.email
            queue_email([to], f"[TEST] {ec.subject}", text, html, kind="marketing", created_by=request.user)
            messages.success(request, f"A test copy was sent to {to}.")
        elif act == "send":
            if request.POST.get("confirm") != "yes" or request.POST.get("count") != str(aud):
                messages.error(request, "Confirm the recipient count to send.")
            elif not es.smtp_configured:
                messages.error(request, "Email isn't configured yet.")
            elif ec.status in ("sent", "sending"):
                messages.error(request, "This campaign was already sent.")
            elif aud == 0:
                messages.error(request, "There are no subscribed contacts with recorded consent.")
            else:
                n = mk.send_campaign(ec, request.user)
                log_activity(request.user, "email_campaign.sent", ec, f"{n} recipients", request, security=True)
                messages.success(request, f"Queued for {n} subscribers. Delivery status appears in the Email inbox → Outbox.")
                return redirect("dashboard:list", mslug="email-campaigns")
        return redirect("dashboard:email_campaign_send", pk=pk)
    return render(request, "dashboard/email_campaign_send.html", ctx)


@needs("campaigns", "create")
def subscribers_import(request):
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError

    if request.method == "POST":
        if not request.POST.get("consent"):
            messages.error(request, "Confirm that these contacts gave consent to receive marketing email.")
        else:
            raw = request.POST.get("emails", "")
            source = clean_plain(request.POST.get("source", ""), 120) or "Imported by staff"
            added = skipped = 0
            for line in raw.replace(";", "\n").replace(",", "\n").splitlines():
                e = line.strip().lower()
                if not e:
                    continue
                try:
                    validate_email(e)
                except ValidationError:
                    skipped += 1
                    continue
                s, created = Subscriber.objects.get_or_create(email=e, defaults={"consent_at": timezone.now(), "consent_source": source})
                added += created
                skipped += not created
            log_activity(request.user, "subscribers.imported", None, f"{added} added, {skipped} skipped", request)
            messages.success(request, f"{added} subscriber(s) added, {skipped} skipped (duplicates or invalid).")
            return redirect("dashboard:list", mslug="subscribers")
    return render(request, "dashboard/subscribers_import.html", {"page_title": "Import subscribers", "crumbs": [("Dashboard", "/dashboard/"), ("Subscribers", "/dashboard/subscribers/"), ("Import", "")]})
