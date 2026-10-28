"""Proposals: builder, send to client, track views / responses, confirm wins."""
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django import forms
from django.conf import settings as dj
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.cms.models import CaseStudy, Project, Service, Testimonial
from apps.core.sanitize import clean_plain
from apps.core.services import log_activity
from apps.leads.models import Lead
from apps.outbound.models import OutboundSettings, Proposal, ProposalEvent, ProposalItem, Prospect
from apps.billing.services import current_profile, proposal_billing
from .mixins import needs

log = logging.getLogger(__name__)
CRUMB = ("Proposals", "/dashboard/proposals/")


def _dec(v, default=0, hi=Decimal("99999999")):
    try:
        d = Decimal(str(v).replace(",", "").strip() or default)
    except (InvalidOperation, ValueError):
        return Decimal(default)
    return max(Decimal(0), min(d, hi))


@needs("proposals", "view")
def proposals_list(request):
    g = request.GET
    qs = Proposal.objects.select_related("lead")
    if g.get("q"):
        qs = qs.filter(Q(title__icontains=g["q"]) | Q(client_name__icontains=g["q"]) | Q(client_company__icontains=g["q"]) | Q(reference__icontains=g["q"]))
    if g.get("status"):
        qs = qs.filter(status=g["status"])
    counts = {k: Proposal.objects.filter(status=k).count() for k, _ in Proposal.STATUS}
    page = Paginator(qs.prefetch_related("items"), 20).get_page(g.get("page"))
    qd = g.copy()
    qd.pop("page", None)
    return render(request, "dashboard/outbound/proposals.html", {
        "page": page, "g": g, "qs": qd.urlencode(), "statuses": Proposal.STATUS, "counts": counts, "total": sum(counts.values()), "can_create": request.user.can("proposals", "create"),
        "page_title": "Proposals", "crumbs": [("Dashboard", "/dashboard/"), ("Outbound Sales", "/dashboard/outbound/"), ("Proposals", "")],
    })


class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ["title", "client_name", "client_company", "client_email", "client_website", "intro", "scope", "terms", "currency", "discount", "tax_percent", "valid_until", "show_portfolio", "show_case_studies", "show_testimonials"]
        widgets = {"intro": forms.Textarea(attrs={"rows": 4}), "scope": forms.Textarea(attrs={"rows": 6}), "terms": forms.Textarea(attrs={"rows": 4}),
                   "valid_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["show_portfolio"].queryset = Project.objects.live()
        self.fields["show_case_studies"].queryset = CaseStudy.objects.live()
        self.fields["show_testimonials"].queryset = Testimonial.objects.filter(is_published=True) if hasattr(Testimonial, "is_published") else Testimonial.objects.all()
        for n, f in self.fields.items():
            f.widget.attrs["class"] = "input multi" if isinstance(f.widget, forms.SelectMultiple) else "input"
            if isinstance(f.widget, forms.SelectMultiple):
                f.widget.attrs["size"] = 5
        self.fields["show_portfolio"].help_text = "Optional: published portfolio projects shown on the proposal page as proof of work."
        self.fields["show_case_studies"].help_text = "Optional: published case studies."
        self.fields["show_testimonials"].help_text = "Optional: client testimonials."

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "USD").upper()[:3]

    def clean_tax_percent(self):
        v = self.cleaned_data.get("tax_percent") or 0
        if not 0 <= v <= 100:
            raise forms.ValidationError("Tax must be between 0 and 100.")
        return v


def _read_items(post):
    rows = []
    for i, (desc, detail, qty, price, svc) in enumerate(zip(post.getlist("item_desc"), post.getlist("item_detail"), post.getlist("item_qty"), post.getlist("item_price"), post.getlist("item_service"))):
        desc = clean_plain(desc, 300)
        if not desc:
            continue
        rows.append({"description": desc, "detail": clean_plain(detail, 500), "quantity": _dec(qty, 1, Decimal("9999")) or Decimal(1), "unit_price": _dec(price), "order": i,
                     "service": Service.objects.filter(pk=svc).first() if str(svc).isdigit() else None})
    return rows


@needs("proposals", "create")
def proposal_new(request):
    return _builder(request, None)


@needs("proposals", "edit")
def proposal_edit(request, pk):
    return _builder(request, get_object_or_404(Proposal, pk=pk))


def _builder(request, pr):
    cfg = OutboundSettings.load()
    initial = {}
    if pr is None:
        lead = Lead.objects.filter(pk=request.GET.get("lead")).first() if request.GET.get("lead", "").isdigit() else None
        prospect = Prospect.objects.filter(pk=request.GET.get("prospect")).first() if request.GET.get("prospect", "").isdigit() else None
        initial = {"currency": cfg.currency, "valid_until": timezone.localdate() + timedelta(days=cfg.proposal_valid_days), "intro": "Thank you for the opportunity. Here is our proposal for your project."}
        if lead:
            initial.update(title=f"Proposal for {lead.name}", client_name=lead.name, client_email=lead.email)
        elif prospect:
            initial.update(title=f"Proposal for {prospect.business_name}", client_name=prospect.business_name, client_company=prospect.business_name, client_email=prospect.email, client_website=prospect.website)
    else:
        lead, prospect = pr.lead, pr.prospect
        if pr.status not in (Proposal.DRAFT,) and request.method == "GET":
            messages.info(request, "This proposal was already sent. Changes will be visible to the client immediately – tell them if you change prices.")
    form = ProposalForm(request.POST or None, instance=pr, initial=initial)
    items = _read_items(request.POST) if request.method == "POST" else ([{"description": i.description, "detail": i.detail, "quantity": i.quantity, "unit_price": i.unit_price, "service": i.service} for i in pr.items.all()] if pr else [])
    if request.method == "POST":
        if not items:
            form.add_error(None, "Add at least one line item.")
        if form.is_valid() and items:
            obj = form.save(commit=False)
            if pr is None:
                obj.created_by, obj.lead, obj.prospect = request.user, lead, prospect
            if obj.discount < 0:
                obj.discount = 0
            obj.save()
            form.save_m2m()
            obj.items.all().delete()
            ProposalItem.objects.bulk_create([ProposalItem(proposal=obj, **r) for r in items])
            if obj.discount > obj.subtotal:
                obj.discount = obj.subtotal
                obj.save(update_fields=["discount"])
            ProposalEvent.objects.create(proposal=obj, kind="created" if pr is None else "edited", actor=request.user, detail="Draft saved" if pr is None else "Edited")
            log_activity(request.user, "proposal.saved", obj, obj.reference, request)
            messages.success(request, "Proposal saved.")
            return redirect("dashboard:proposal_detail", pk=obj.pk)
    services = Service.objects.live().order_by("order", "title")
    return render(request, "dashboard/outbound/proposal_form.html", {
        "form": form, "items": items, "pr": pr, "services": services, "lead": lead, "prospect": prospect,
        "page_title": "Proposal builder", "crumbs": [("Dashboard", "/dashboard/"), ("Proposals", "/dashboard/proposals/"), (pr.reference if pr else "New", "")],
    })


@needs("proposals", "view")
def proposal_detail(request, pk):
    pr = get_object_or_404(Proposal.objects.select_related("lead", "prospect", "created_by").prefetch_related("items"), pk=pk)
    return render(request, "dashboard/outbound/proposal_detail.html", {
        "pr": pr, "events": pr.events.select_related("actor")[:30], "public_url": f"{dj.SITE_URL}{pr.public_path}",
        "can_edit": request.user.can("proposals", "edit"), "can_delete": request.user.can("proposals", "delete"), "can_approve": request.user.can("proposals", "approve"),
        "billing": proposal_billing(pr), "can_invoice": request.user.can("invoices", "create"), "profile_doc": current_profile(),
        "page_title": pr.reference, "crumbs": [("Dashboard", "/dashboard/"), ("Proposals", "/dashboard/proposals/"), (pr.reference, "")],
    })


@needs("proposals", "edit")
@require_POST
def proposal_action(request, pk):
    pr = get_object_or_404(Proposal, pk=pk)
    act, u = request.POST.get("action"), request.user
    back = redirect("dashboard:proposal_detail", pk=pr.pk)
    if act == "send":
        if not pr.client_email:
            messages.error(request, "Add the client's email address first.")
            return back
        if not pr.items.exists():
            messages.error(request, "Add line items first.")
            return back
        from apps.mailer.service import queue_email, reply_to_lead
        from apps.outbound.services import is_suppressed

        link = f"{dj.SITE_URL}{pr.public_path}"
        cfg = OutboundSettings.load()
        if pr.client_website:
            link += f"\n\nWebsite this proposal is about: {pr.client_website}"
        body = (f"Hi {pr.client_name.split(' ')[0]},\n\nThank you for your interest in working with {cfg.sender_business}. Your proposal “{pr.title}” ({pr.reference}) is ready:\n\n{link}\n\n"
                f"It is valid until {pr.valid_until:%d %B %Y}. Reply to this email with any questions.\n\n{cfg.sender_name or cfg.sender_business}" if pr.valid_until else
                f"Hi {pr.client_name.split(' ')[0]},\n\nYour proposal “{pr.title}” ({pr.reference}) is ready:\n\n{link}\n\nReply to this email with any questions.\n\n{cfg.sender_name or cfg.sender_business}")
        doc, refs, mode = None, [], request.POST.get("profile_mode", "none")
        if mode in ("attach", "link"):
            doc = current_profile()
            if not doc or (mode == "attach" and not doc.asset_id):
                messages.error(request, "No company profile PDF is available. Select one under Billing → Company profile PDF, or send without it.")
                return back
            if mode == "attach":
                refs = [{"kind": "media", "id": doc.asset_id}]
            else:
                body += f"\n\nCompany profile (secure link): {dj.SITE_URL}{doc.link_path}"
        if pr.lead_id:
            msg = reply_to_lead(pr.lead, u, f"Your proposal: {pr.title}", body, attachments=refs or None)
        else:
            if is_suppressed(pr.client_email):
                messages.error(request, "This address is on the do-not-contact list.")
                return back
            msg = queue_email([pr.client_email], f"Your proposal: {pr.title}", body, kind="reply", created_by=u, attachments=refs or None)
        if doc:
            from apps.billing.models import DocumentShare
            DocumentShare.objects.create(document=doc, mode=mode, proposal=pr, lead=pr.lead, email=msg, created_by=u)
        pr.status, pr.sent_at = Proposal.SENT, timezone.now()
        pr.save(update_fields=["status", "sent_at", "updated_at"])
        if pr.lead and pr.lead.status in (Lead.NEW, Lead.CONTACTED, Lead.QUALIFIED):
            pr.lead.status = Lead.PROPOSAL
            pr.lead.save(update_fields=["status", "updated_at"])
        ProposalEvent.objects.create(proposal=pr, kind="sent", actor=u, detail=f"Emailed to {pr.client_email}")
        log_activity(u, "proposal.sent", pr, pr.client_email, request)
        messages.success(request, "Proposal emailed to the client. You'll get an alert when they open it.")
    elif act == "mark_sent":
        pr.status, pr.sent_at = Proposal.SENT, pr.sent_at or timezone.now()
        pr.save(update_fields=["status", "sent_at", "updated_at"])
        ProposalEvent.objects.create(proposal=pr, kind="sent", actor=u, detail="Marked as sent (shared the link yourself)")
        messages.success(request, "Marked as sent. Share the link with the client.")
    elif act in ("won", "lost"):
        if not u.can("proposals", "approve"):
            messages.error(request, "You don't have permission to confirm outcomes.")
            return back
        pr.status = Proposal.WON if act == "won" else Proposal.DECLINED
        pr.responded_at = pr.responded_at or timezone.now()
        pr.save(update_fields=["status", "responded_at", "updated_at"])
        if pr.lead:
            pr.lead.status = Lead.WON if act == "won" else Lead.LOST
            pr.lead.save(update_fields=["status", "updated_at"])
        ProposalEvent.objects.create(proposal=pr, kind=act, actor=u, detail="Confirmed by staff")
        log_activity(u, f"proposal.{act}", pr, pr.reference, request)
        messages.success(request, "Marked as won – the lead is now Won." if act == "won" else "Marked as lost.")
    elif act == "reopen":
        pr.status = Proposal.SENT if pr.sent_at else Proposal.DRAFT
        pr.responded_at = None
        pr.save(update_fields=["status", "responded_at", "updated_at"])
    elif act == "note":
        body = clean_plain(request.POST.get("body", ""), 300)
        if body:
            ProposalEvent.objects.create(proposal=pr, kind="note", actor=u, detail=body)
    elif act == "duplicate":
        items = list(pr.items.all())
        new = Proposal.objects.create(title=f"{pr.title} (copy)", client_name=pr.client_name, client_company=pr.client_company, client_email=pr.client_email, client_website=pr.client_website, lead=pr.lead, prospect=pr.prospect,
                                      currency=pr.currency, intro=pr.intro, scope=pr.scope, terms=pr.terms, discount=pr.discount, tax_percent=pr.tax_percent, created_by=u,
                                      valid_until=timezone.localdate() + timedelta(days=OutboundSettings.load().proposal_valid_days))
        ProposalItem.objects.bulk_create([ProposalItem(proposal=new, service=i.service, description=i.description, detail=i.detail, quantity=i.quantity, unit_price=i.unit_price, order=i.order) for i in items])
        new.show_portfolio.set(pr.show_portfolio.all())
        new.show_case_studies.set(pr.show_case_studies.all())
        new.show_testimonials.set(pr.show_testimonials.all())
        messages.success(request, "Duplicated as a new draft.")
        return redirect("dashboard:proposal_edit", pk=new.pk)
    return back


@needs("proposals", "delete")
@require_POST
def proposal_delete(request, pk):
    pr = get_object_or_404(Proposal, pk=pk)
    log_activity(request.user, "proposal.deleted", pr, pr.reference, request)
    pr.delete()
    messages.success(request, "Proposal deleted. Its link no longer works.")
    return redirect("dashboard:proposals")
