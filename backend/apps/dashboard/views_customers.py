import csv
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.blog.models import Comment, Post
from apps.chatbot import engine
from apps.chatbot.models import ChatMessage, Conversation
from apps.core.models import ActivityLog
from apps.core.sanitize import clean_plain
from apps.core.services import bump_content_version, log_activity
from apps.leads.models import Lead, LeadNote
from apps.mailer import inbound, service as mailer
from apps.mailer.models import PROVIDER_PRESETS, EmailMessage, EmailSettings, EmailThread
from .mixins import forbidden, needs

STAFF_QS = lambda: User.objects.filter(status="approved", is_active=True).order_by("full_name")


# =================================================================== LEADS
def _lead_filter(request):
    qs = Lead.objects.select_related("assigned_to", "service")
    g = request.GET
    spam = g.get("spam") == "1"
    qs = qs.filter(is_spam=spam)
    if g.get("status"):
        qs = qs.filter(status=g["status"])
    if g.get("source"):
        qs = qs.filter(source=g["source"])
    if g.get("category") in dict(Lead.CATEGORIES):
        qs = qs.filter(category=g["category"])
    if g.get("assigned") == "me":
        qs = qs.filter(assigned_to=request.user)
    elif g.get("assigned") == "none":
        qs = qs.filter(assigned_to__isnull=True)
    elif g.get("assigned", "").isdigit():
        qs = qs.filter(assigned_to_id=g["assigned"])
    if g.get("followup") == "due":
        qs = qs.filter(follow_up_at__lte=timezone.now()).exclude(status__in=["won", "lost", "archived"])
    if g.get("q"):
        q = g["q"].strip()
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q) | Q(reference__icontains=q) | Q(message__icontains=q) | Q(service_label__icontains=q))
    if g.get("from"):
        qs = qs.filter(created_at__date__gte=g["from"])
    if g.get("to"):
        qs = qs.filter(created_at__date__lte=g["to"])
    return qs


@needs("leads", "view")
def leads_list(request):
    qs = _lead_filter(request)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    counts = {k: Lead.objects.filter(is_spam=False, status=k).count() for k, _ in Lead.STATUS_CHOICES}
    qd = request.GET.copy()
    qd.pop("page", None)
    return render(request, "dashboard/leads_list.html", {
        "page": page, "counts": counts, "total": sum(counts.values()), "statuses": Lead.STATUS_CHOICES, "sources": Lead.SOURCES, "categories": Lead.CATEGORIES, "staff": STAFF_QS(),
        "g": request.GET, "qs": qd.urlencode(), "spam_count": Lead.objects.filter(is_spam=True).count(),
        "can_export": request.user.can("leads", "export"), "can_create": request.user.can("leads", "create"), "can_edit": request.user.can("leads", "edit"),
        "page_title": "Leads & messages", "crumbs": [("Dashboard", "/dashboard/"), ("Leads & messages", "")],
    })


@needs("leads", "export")
def leads_export(request):
    qs = _lead_filter(request).order_by("-created_at")
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="leads-{timezone.now():%Y%m%d-%H%M}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    safe = lambda v: ("'" + str(v)) if str(v)[:1] in ("=", "+", "-", "@") else ("" if v is None else str(v))
    w.writerow(["reference", "created", "name", "email", "phone", "service", "budget", "status", "assigned_to", "source", "source_page", "utm_source", "utm_campaign", "message"])
    for l in qs.iterator():
        w.writerow([l.reference, l.created_at.strftime("%Y-%m-%d %H:%M"), safe(l.name), safe(l.email), safe(l.full_phone), safe(l.service_label), safe(l.budget_label), l.status,
                    safe(l.assigned_to.email if l.assigned_to else ""), l.source, safe(l.source_page), safe(l.utm_source), safe(l.utm_campaign), safe(l.message)])
    log_activity(request.user, "leads.exported", None, f"{qs.count()} rows", request, security=True)
    return resp


class ManualLeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["name", "email", "country_code", "phone", "service_label", "budget_label", "message", "source", "assigned_to"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["source"].choices = [("manual", "Added manually"), ("email", "Inbound email")]
        self.fields["assigned_to"].queryset = STAFF_QS()
        for f in self.fields.values():
            f.widget.attrs["class"] = "input"


@needs("leads", "create")
def lead_create(request):
    form = ManualLeadForm(request.POST or None, initial={"source": "manual"})
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.name, lead.message = clean_plain(lead.name, 120), clean_plain(lead.message, 4000)
        lead.save()
        log_activity(request.user, "lead.created", lead, "manual", request)
        messages.success(request, f"Lead {lead.reference} created.")
        return redirect("dashboard:lead_detail", pk=lead.pk)
    return render(request, "dashboard/lead_new.html", {"form": form, "page_title": "Add lead", "crumbs": [("Dashboard", "/dashboard/"), ("Leads & messages", "/dashboard/leads/"), ("Add lead", "")]})


@needs("leads", "view")
def lead_detail(request, pk):
    lead = get_object_or_404(Lead.objects.select_related("assigned_to", "service", "budget"), pk=pk)
    thread = EmailThread.objects.filter(lead=lead).first()
    emails = EmailMessage.objects.filter(Q(lead=lead) | Q(thread=thread) if thread else Q(lead=lead)).order_by("created_at")
    timeline = ActivityLog.objects.filter(target_type="Lead", target_id=str(lead.pk)).select_related("actor")[:25]
    es = EmailSettings.load()
    return render(request, "dashboard/lead_detail.html", {
        "lead": lead, "notes": lead.notes.select_related("author"), "emails": emails, "timeline": timeline, "staff": STAFF_QS(), "statuses": Lead.STATUS_CHOICES,
        "conversations": lead.conversations.all(), "smtp_ready": es.smtp_configured, "can_edit": request.user.can("leads", "edit"), "can_reply": request.user.can("email", "create"),
        "can_delete": request.user.can("leads", "delete"), "can_approve": request.user.can("leads", "approve"),
        "categories": Lead.CATEGORIES, "can_propose": request.user.can("proposals", "create"), "can_invoice": request.user.can("invoices", "create"),
        "default_subject": f"Re: your enquiry to AUB SQUARE", "page_title": lead.reference,
        "crumbs": [("Dashboard", "/dashboard/"), ("Leads & messages", "/dashboard/leads/"), (lead.reference, "")],
    })


@needs("leads", "edit")
@require_POST
def lead_update(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    act = request.POST.get("action")
    if act == "status":
        new = request.POST.get("status")
        if new in dict(Lead.STATUS_CHOICES) and new != lead.status:
            old, lead.status = lead.status, new
            lead.save(update_fields=["status", "updated_at"])
            if old == Lead.NEW:
                from apps.outbound.services import mark_first_response

                mark_first_response(lead)
            log_activity(request.user, "lead.status", lead, f"{old} → {new}", request)
            messages.success(request, f"Status changed to {lead.get_status_display()}.")
    elif act == "category":
        new = request.POST.get("category")
        if new in dict(Lead.CATEGORIES):
            lead.category = new
            lead.save(update_fields=["category", "updated_at"])
            messages.success(request, f"Grouped under {lead.get_category_display()}.")
    elif act == "assign":
        uid = request.POST.get("assigned_to")
        new = STAFF_QS().filter(pk=uid).first() if uid else None
        lead.assigned_to = new
        lead.save(update_fields=["assigned_to", "updated_at"])
        log_activity(request.user, "lead.assigned", lead, new.email if new else "unassigned", request)
        if new and new.pk != request.user.pk:
            from apps.core.services import notify_user

            notify_user(new, "lead", f"Lead assigned to you: {lead.name}", lead.service_label, f"/dashboard/leads/{lead.pk}/", "info")
        messages.success(request, "Assignment updated.")
    elif act == "followup":
        raw = request.POST.get("follow_up_at", "")
        dt = parse_datetime(raw) if raw else None
        if dt and timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        lead.follow_up_at, lead.follow_up_note = dt, clean_plain(request.POST.get("follow_up_note", ""), 300)
        lead.save(update_fields=["follow_up_at", "follow_up_note", "updated_at"])
        log_activity(request.user, "lead.followup", lead, str(dt or "cleared"), request)
        messages.success(request, "Follow-up saved." if dt else "Follow-up cleared.")
    elif act == "note":
        body = clean_plain(request.POST.get("body", ""), 3000)
        if body:
            LeadNote.objects.create(lead=lead, author=request.user, body=body)
            log_activity(request.user, "lead.note", lead, "", request)
            messages.success(request, "Note added.")
    elif act == "spam":
        lead.is_spam = not lead.is_spam
        lead.save(update_fields=["is_spam", "updated_at"])
        log_activity(request.user, "lead.spam" if lead.is_spam else "lead.notspam", lead, "", request)
        messages.success(request, "Marked as spam." if lead.is_spam else "Restored from spam.")
    return redirect("dashboard:lead_detail", pk=pk)


@needs("email", "create")
@require_POST
def lead_reply(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    es = EmailSettings.load()
    subject, body = clean_plain(request.POST.get("subject", ""), 200), request.POST.get("body", "").strip()[:8000]
    if not subject or not body:
        messages.error(request, "Add a subject and a message.")
    elif not es.smtp_configured:
        messages.error(request, "Email isn't configured yet. Add SMTP details in Email settings first.")
    else:
        mailer.reply_to_lead(lead, request.user, subject, body)
        log_activity(request.user, "lead.reply", lead, subject[:100], request)
        messages.success(request, "Reply queued for delivery. Delivery status is shown in the conversation below.")
    return redirect(reverse("dashboard:lead_detail", args=[pk]) + "#emails")


@needs("leads", "delete")
@require_POST
def lead_delete(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    log_activity(request.user, "lead.deleted", lead, lead.reference, request, security=True)
    lead.delete()
    messages.success(request, "Lead deleted.")
    return redirect("dashboard:leads")


@needs("leads", "edit")
@require_POST
def leads_bulk(request):
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    act, val = request.POST.get("action"), request.POST.get("value", "")
    qs = Lead.objects.filter(pk__in=ids)
    n = 0
    if act == "status" and val in dict(Lead.STATUS_CHOICES):
        n = qs.update(status=val, updated_at=timezone.now())
    elif act == "assign" and val.isdigit() and STAFF_QS().filter(pk=val).exists():
        n = qs.update(assigned_to_id=val, updated_at=timezone.now())
    elif act == "delete":
        if not request.user.can("leads", "delete"):
            return forbidden(request)
        n = qs.count()
        qs.delete()
    if n:
        log_activity(request.user, f"leads.bulk_{act}", None, f"{n} leads {val}", request)
        messages.success(request, f"{n} lead{'s' if n != 1 else ''} updated.")
    return redirect(request.POST.get("next") or "dashboard:leads")


# =================================================================== COMMENTS
@needs("blog", "view")
def comments_list(request):
    status = request.GET.get("status", "pending")
    qs = Comment.objects.select_related("post", "parent", "moderated_by")
    if status != "all":
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(body__icontains=q) | Q(post__title__icontains=q))
    qs = qs.order_by("-created_at")
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    counts = {k: Comment.objects.filter(status=k).count() for k, _ in Comment.STATUS}
    return render(request, "dashboard/comments.html", {"page": page, "status": status, "counts": counts, "statuses": Comment.STATUS, "q": q,
                                                      "can_moderate": request.user.can("blog", "approve"), "can_delete": request.user.can("blog", "delete"),
                                                      "page_title": "Comments", "crumbs": [("Dashboard", "/dashboard/"), ("Blog", "/dashboard/posts/"), ("Comments", "")]})


@needs("blog", "approve")
@require_POST
def comment_action(request, pk):
    c = get_object_or_404(Comment, pk=pk)
    act = request.POST.get("action")
    mapping = {"approve": Comment.APPROVED, "reject": Comment.REJECTED, "spam": Comment.SPAM, "pending": Comment.PENDING}
    if act in mapping:
        c.status, c.moderated_by, c.moderated_at = mapping[act], request.user, timezone.now()
        c.save()
        bump_content_version()
        log_activity(request.user, f"comment.{act}", c, c.body[:80], request)
        messages.success(request, f"Comment {act}d." if act != "spam" else "Comment marked as spam.")
    elif act == "reply":
        body = clean_plain(request.POST.get("body", ""), 2000)
        if body:
            root = c.parent or c
            Comment.objects.create(post=c.post, parent=root, name=request.user.display_name, email=request.user.email, body=body, status=Comment.APPROVED,
                                   is_staff_reply=True, moderated_by=request.user, moderated_at=timezone.now())
            if c.status == Comment.PENDING:
                c.status = Comment.APPROVED
                c.save()
            bump_content_version()
            log_activity(request.user, "comment.reply", c, body[:80], request)
            messages.success(request, "Reply published.")
    return redirect(request.POST.get("next") or "dashboard:comments")


@needs("blog", "delete")
@require_POST
def comment_delete(request, pk):
    c = get_object_or_404(Comment, pk=pk)
    log_activity(request.user, "comment.deleted", c, c.body[:80], request)
    c.delete()
    bump_content_version()
    messages.success(request, "Comment deleted.")
    return redirect(request.POST.get("next") or "dashboard:comments")


# =================================================================== CHAT
def _chat_msg(m):
    return {"id": m.pk, "sender": m.sender, "body": m.body, "at": m.created_at.isoformat(), "agent": m.agent.display_name if m.agent_id else ""}


@needs("chatbot", "view")
def chat_list(request):
    status = request.GET.get("status", "open")
    qs = Conversation.objects.select_related("assigned_to", "lead")
    if status == "open":
        qs = qs.filter(status__in=["waiting", "active"])
    elif status in dict(Conversation.STATUS):
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(visitor_name__icontains=q) | Q(visitor_email__icontains=q) | Q(last_message_preview__icontains=q))
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    counts = {"open": Conversation.objects.filter(status__in=["waiting", "active"]).count(), **{k: Conversation.objects.filter(status=k).count() for k, _ in Conversation.STATUS}}
    return render(request, "dashboard/chat_list.html", {"page": page, "status": status, "counts": counts, "q": q, "statuses": Conversation.STATUS,
                                                       "page_title": "Chatbot & live chat", "crumbs": [("Dashboard", "/dashboard/"), ("Chatbot & live chat", "")]})


@needs("chatbot", "view")
def chat_detail(request, pk):
    conv = get_object_or_404(Conversation.objects.select_related("assigned_to", "lead"), pk=pk)
    if conv.unread_for_agent:
        conv.unread_for_agent = 0
        conv.save(update_fields=["unread_for_agent"])
    msgs = list(conv.messages.select_related("agent"))
    return render(request, "dashboard/chat_detail.html", {"conv": conv, "msgs": msgs, "last_id": msgs[-1].pk if msgs else 0, "staff": STAFF_QS(),
                                                          "can_reply": request.user.can("chatbot", "edit"),
                                                          "page_title": str(conv), "crumbs": [("Dashboard", "/dashboard/"), ("Chatbot & live chat", "/dashboard/chat/"), (str(conv), "")]})


@needs("chatbot", "view")
def chat_poll(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    after = int(request.GET.get("after", 0) or 0)
    msgs = conv.messages.filter(id__gt=after).select_related("agent")
    if conv.unread_for_agent:
        Conversation.objects.filter(pk=pk).update(unread_for_agent=0)
    return JsonResponse({"status": conv.status, "messages": [_chat_msg(m) for m in msgs]})


@needs("chatbot", "edit")
@require_POST
def chat_reply(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    body = clean_plain(request.POST.get("body", ""), 1500)
    ajax = request.headers.get("x-requested-with") == "fetch"
    if not body:
        return JsonResponse({"error": "Empty message"}, status=400) if ajax else redirect("dashboard:chat_detail", pk=pk)
    if conv.status == Conversation.CLOSED:
        conv.status = Conversation.ACTIVE
    else:
        conv.status = Conversation.ACTIVE
    if not conv.assigned_to_id:
        conv.assigned_to = request.user
    conv.save(update_fields=["status", "assigned_to", "updated_at"])
    msg = engine.add_message(conv, ChatMessage.AGENT, body, agent=request.user)
    log_activity(request.user, "chat.reply", conv, "", request)
    if ajax:
        return JsonResponse({"message": _chat_msg(msg)})
    return redirect("dashboard:chat_detail", pk=pk)


@needs("chatbot", "edit")
@require_POST
def chat_action(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    act = request.POST.get("action")
    if act == "close":
        conv.status = Conversation.CLOSED
        conv.save(update_fields=["status", "updated_at"])
        engine.add_message(conv, ChatMessage.SYSTEM, "This conversation was closed by our team. Start a new chat any time.")
        messages.success(request, "Conversation closed.")
    elif act == "reopen":
        conv.status = Conversation.ACTIVE
        conv.save(update_fields=["status", "updated_at"])
    elif act == "assign":
        u = STAFF_QS().filter(pk=request.POST.get("assigned_to") or 0).first()
        conv.assigned_to = u
        conv.save(update_fields=["assigned_to", "updated_at"])
        messages.success(request, "Assignment updated.")
    elif act == "to_lead":
        if not request.user.can("leads", "create"):
            return forbidden(request)
        if not conv.visitor_email:
            messages.error(request, "This visitor hasn't shared an email address yet, so a lead can't be created.")
        else:
            lead = engine.lead_from_conversation(conv, request)
            messages.success(request, f"Lead {lead.reference} created from this chat.")
            return redirect("dashboard:lead_detail", pk=lead.pk)
    log_activity(request.user, f"chat.{act}", conv, "", request)
    return redirect("dashboard:chat_detail", pk=pk)


@needs("chatbot", "delete")
@require_POST
def chat_delete(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    log_activity(request.user, "chat.deleted", conv, "", request, security=True)
    conv.delete()
    messages.success(request, "Conversation deleted.")
    return redirect("dashboard:chat")


# =================================================================== EMAIL INBOX
@needs("email", "view")
def inbox(request):
    tab = request.GET.get("tab", "inbox")
    q = request.GET.get("q", "").strip()
    if tab in ("outbox", "failed"):
        qs = EmailMessage.objects.filter(direction="out").select_related("lead", "created_by")
        if tab == "failed":
            qs = qs.filter(status="failed")
        elif request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("kind"):
            qs = qs.filter(kind=request.GET["kind"])
        else:
            qs = qs.exclude(kind__in=["account"]) if not request.user.is_superuser else qs
        if q:
            qs = qs.filter(Q(subject__icontains=q) | Q(body_text__icontains=q))
        page = Paginator(qs.order_by("-created_at"), 25).get_page(request.GET.get("page"))
        kind = "messages"
    else:
        qs = EmailThread.objects.select_related("lead", "assigned_to").annotate(msg_count=Count("messages"))
        if tab == "unread":
            qs = qs.filter(has_unread=True)
        if tab == "inbox":
            qs = qs.filter(messages__direction="in").distinct()
        if q:
            qs = qs.filter(Q(subject__icontains=q) | Q(participant__icontains=q))
        page = Paginator(qs.order_by("-last_message_at"), 25).get_page(request.GET.get("page"))
        kind = "threads"
    es = EmailSettings.load()
    counts = {
        "unread": EmailThread.objects.filter(has_unread=True).count(),
        "failed": EmailMessage.objects.filter(direction="out", status="failed").count(),
        "queued": EmailMessage.objects.filter(direction="out", status__in=["queued", "sending"]).count(),
    }
    return render(request, "dashboard/inbox.html", {"page": page, "kind": kind, "tab": tab, "q": q, "es": es, "counts": counts, "status_choices": EmailMessage.STATUS, "kinds": EmailMessage.KINDS,
                                                    "can_compose": request.user.can("email", "create"), "can_sync": request.user.can("email", "edit"),
                                                    "page_title": "Email inbox", "crumbs": [("Dashboard", "/dashboard/"), ("Email inbox", "")]})


@needs("email", "view")
def thread_detail(request, pk):
    t = get_object_or_404(EmailThread.objects.select_related("lead"), pk=pk)
    if t.has_unread:
        t.has_unread = False
        t.save(update_fields=["has_unread"])
        t.messages.filter(direction="in", is_read=False).update(is_read=True)
    msgs = t.messages.select_related("created_by").order_by("created_at")
    last_in = msgs.filter(direction="in").last()
    default_to = (last_in.from_email if last_in else t.participant) or ""
    subject = t.subject if t.subject.lower().startswith("re:") else f"Re: {t.subject}"
    return render(request, "dashboard/thread.html", {"t": t, "msgs": msgs, "default_to": default_to, "reply_subject": subject, "es": EmailSettings.load(),
                                                     "can_reply": request.user.can("email", "create"),
                                                     "page_title": t.subject[:60], "crumbs": [("Dashboard", "/dashboard/"), ("Email inbox", "/dashboard/inbox/"), (t.subject[:40], "")]})


@needs("email", "create")
@require_POST
def thread_reply(request, pk):
    t = get_object_or_404(EmailThread, pk=pk)
    to = request.POST.get("to", "").strip()
    subject, body = clean_plain(request.POST.get("subject", ""), 250), request.POST.get("body", "").strip()[:8000]
    try:
        validate_email(to)
    except ValidationError:
        messages.error(request, "Enter a valid recipient email address.")
        return redirect("dashboard:thread", pk=pk)
    if not body:
        messages.error(request, "Write a message first.")
    elif not EmailSettings.load().smtp_configured:
        messages.error(request, "Email isn't configured yet. Add SMTP details in Email settings first.")
    else:
        last = t.messages.exclude(message_id="").order_by("-created_at").first()
        refs = " ".join(filter(None, [last.references if last else "", last.message_id if last else ""])).strip()
        mailer.queue_email([to], subject, body, kind="reply", lead=t.lead, thread=t, created_by=request.user, in_reply_to=last.message_id if last else "", references=refs)
        t.last_message_at = timezone.now()
        t.save(update_fields=["last_message_at"])
        log_activity(request.user, "email.reply", t, to, request)
        messages.success(request, "Reply queued for delivery.")
    return redirect("dashboard:thread", pk=pk)


class ComposeForm(forms.Form):
    to = forms.EmailField(widget=forms.EmailInput(attrs={"class": "input"}))
    subject = forms.CharField(max_length=250, widget=forms.TextInput(attrs={"class": "input"}))
    body = forms.CharField(widget=forms.Textarea(attrs={"class": "input", "rows": 10}))


@needs("email", "create")
def compose(request):
    form = ComposeForm(request.POST or None, initial={"to": request.GET.get("to", ""), "subject": request.GET.get("subject", "")})
    if request.method == "POST" and form.is_valid():
        if not EmailSettings.load().smtp_configured:
            messages.error(request, "Email isn't configured yet. Add SMTP details in Email settings first.")
        else:
            d = form.cleaned_data
            thread = EmailThread.objects.create(subject=d["subject"], participant=d["to"])
            mailer.queue_email([d["to"]], d["subject"], d["body"], kind="reply", thread=thread, created_by=request.user)
            log_activity(request.user, "email.composed", thread, d["to"], request)
            messages.success(request, "Email queued for delivery.")
            return redirect("dashboard:thread", pk=thread.pk)
    return render(request, "dashboard/compose.html", {"form": form, "page_title": "Compose email", "crumbs": [("Dashboard", "/dashboard/"), ("Email inbox", "/dashboard/inbox/"), ("Compose", "")]})


@needs("email", "view")
def message_detail(request, pk):
    m = get_object_or_404(EmailMessage.objects.select_related("lead", "thread", "created_by"), pk=pk)
    return render(request, "dashboard/message.html", {"m": m, "can_retry": request.user.can("email", "edit"), "page_title": m.subject[:60],
                                                      "crumbs": [("Dashboard", "/dashboard/"), ("Email inbox", "/dashboard/inbox/"), (m.subject[:40], "")]})


@needs("email", "edit")
@require_POST
def message_retry(request, pk):
    m = get_object_or_404(EmailMessage, pk=pk, direction="out")
    if m.status == "sent":
        messages.info(request, "This message was already delivered.")
    else:
        mailer.retry_message(m)
        m.refresh_from_db()
        (messages.success if m.status == "sent" else messages.error)(request, "Delivered." if m.status == "sent" else f"Still failing: {m.error[:200]}")
    return redirect("dashboard:message", pk=pk)


@needs("email", "edit")
@require_POST
def inbox_sync(request):
    try:
        res = inbound.sync_inbox()
        messages.success(request, f"Inbox synced: {res.get('new', 0)} new message(s).")
    except inbound.InboundNotConfigured:
        messages.error(request, "Inbox sync isn't set up. Enable IMAP in Email settings.")
    except Exception as exc:
        messages.error(request, f"Inbox sync failed: {mailer.scrub(str(exc))[:200]}")
    return redirect("dashboard:inbox")


@needs("email", "edit")
@require_POST
def outbox_process(request):
    res = mailer.process_queue()
    messages.success(request, f"Processed queue: {res.get('sent', 0)} sent, {res.get('failed', 0)} failed.")
    return redirect("dashboard:inbox")


# =================================================================== EMAIL SETTINGS
class EmailSettingsForm(forms.ModelForm):
    smtp_password = forms.CharField(required=False, label="SMTP password / app password", widget=forms.PasswordInput(render_value=False, attrs={"class": "input", "autocomplete": "new-password", "placeholder": "Leave blank to keep the saved password"}))
    imap_password = forms.CharField(required=False, label="IMAP password / app password", widget=forms.PasswordInput(render_value=False, attrs={"class": "input", "autocomplete": "new-password", "placeholder": "Leave blank to keep the saved password"}))

    class Meta:
        model = EmailSettings
        fields = ["provider", "smtp_host", "smtp_port", "smtp_security", "smtp_username", "from_email", "from_name", "reply_to", "notification_recipients",
                  "notify_new_lead", "notify_new_chat", "notify_new_comment", "notify_new_staff", "notify_marketing_lead", "notify_system",
                  "imap_enabled", "imap_host", "imap_port", "imap_security", "imap_username", "imap_folder"]
        widgets = {"notification_recipients": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for name, f in self.fields.items():
            if isinstance(f.widget, forms.CheckboxInput):
                f.widget.attrs["class"] = "check"
            elif "class" not in f.widget.attrs:
                f.widget.attrs["class"] = "input"

    def clean(self):
        d = super().clean()
        for k in ("smtp_host", "imap_host"):
            if d.get(k):
                d[k] = d[k].strip().lower()
        for k in ("smtp_username", "imap_username", "from_email"):
            if d.get(k):
                d[k] = d[k].strip()
        # port and encryption must agree or the connection hangs / fails with "wrong version number"
        port, sec = d.get("smtp_port"), d.get("smtp_security")
        if port == 465 and sec == "tls":
            d["smtp_security"] = "ssl"
        elif port in (587, 25) and sec == "ssl":
            d["smtp_security"] = "tls"
        iport, isec = d.get("imap_port"), d.get("imap_security")
        if iport == 993 and isec == "starttls":
            d["imap_security"] = "ssl"
        # Google shows app passwords as "abcd efgh ijkl mnop" – the spaces are not part of the password
        host = (d.get("smtp_host") or "") + " " + (d.get("imap_host") or "")
        for k in ("smtp_password", "imap_password"):
            if d.get(k):
                d[k] = d[k].strip()
                if "gmail" in host or "google" in host:
                    d[k] = d[k].replace(" ", "")
        return d

    def save(self, commit=True):
        obj = super().save(commit=False)
        for k in ("smtp_host", "imap_host", "smtp_username", "imap_username", "from_email", "smtp_security", "imap_security"):
            if self.cleaned_data.get(k) is not None:
                setattr(obj, k, self.cleaned_data[k])
        if self.cleaned_data.get("smtp_password"):
            obj.set_smtp_password(self.cleaned_data["smtp_password"])
        if self.cleaned_data.get("imap_password"):
            obj.set_imap_password(self.cleaned_data["imap_password"])
        if commit:
            obj.save()
        return obj


@needs("email_settings", "view")
def email_settings(request):
    es = EmailSettings.load()
    form = EmailSettingsForm(request.POST or None, instance=es)
    if request.method == "POST":
        if not request.user.can("email_settings", "manage_settings"):
            return forbidden(request)
        if form.is_valid():
            form.save()
            log_activity(request.user, "email_settings.updated", es, "credentials changed" if form.cleaned_data.get("smtp_password") or form.cleaned_data.get("imap_password") else "", request, security=True)
            messages.success(request, "Email settings saved. No test email was sent — use “Send test email” when you're ready.")
            return redirect("dashboard:email_settings")
        messages.error(request, "Please fix the highlighted fields.")
    return render(request, "dashboard/email_settings.html", {
        "form": form, "es": es, "presets_json": __import__("json").dumps({k: {"host": v["smtp_host"], "port": v["smtp_port"], "security": v["smtp_security"], "imap_host": v["imap_host"], "imap_port": v["imap_port"], "imap_security": v["imap_security"], "note": v["note"]} for k, v in PROVIDER_PRESETS.items()}).replace("<", "\\u003c"),
        "provider_note": PROVIDER_PRESETS.get(es.provider, {}).get("note", ""), "can_manage": request.user.can("email_settings", "manage_settings"),
        "page_title": "Email settings", "crumbs": [("Dashboard", "/dashboard/"), ("Email settings", "")],
    })


@needs("email_settings", "manage_settings")
@require_POST
def email_test(request):
    """Only ever sends when a person presses the button and supplies a recipient."""
    to = request.POST.get("to", "").strip()
    try:
        validate_email(to)
    except ValidationError:
        messages.error(request, "Enter a valid email address to send the test to.")
        return redirect("dashboard:email_settings")
    ok, msg = mailer.send_test_email(to, request.user)
    log_activity(request.user, "email_settings.test", None, f"{to} → {'ok' if ok else 'failed'}", request, security=True)
    (messages.success if ok else messages.error)(request, msg)
    return redirect("dashboard:email_settings")


@needs("email_settings", "manage_settings")
@require_POST
def imap_test(request):
    try:
        messages.success(request, inbound.test_connection())
    except inbound.InboundNotConfigured:
        messages.error(request, "Fill in the IMAP host, username and password and tick “Enable inbox sync” first.")
    except Exception as exc:
        messages.error(request, f"Could not connect: {mailer.scrub(str(exc))[:200]}")
    return redirect("dashboard:email_settings")
