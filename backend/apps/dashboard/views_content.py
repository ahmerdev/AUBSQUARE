import json

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.cms import home_schema as HS
from apps.cms.models import HomeSection
from apps.core.media import create_media_asset, media_usage, media_used_ids
from apps.core.models import MediaAsset
from apps.core.services import log_activity
from . import widgets as W
from .mixins import forbidden, needs


# =================================================================== HOME PAGE BUILDER
def _section_form(spec, data=None, initial=None):
    fields = {}
    for fd in spec["fields"]:
        t, name = fd["type"], fd["name"]
        if t == HS.TA:
            fields[name] = forms.CharField(label=fd["label"], required=False, help_text=fd["help"], widget=forms.Textarea(attrs={"rows": 3, "class": "input"}))
        elif t == HS.IMG:
            fields[name] = forms.CharField(label=fd["label"], required=False, help_text=fd["help"], widget=W.MediaPickerWidget())
        elif t == HS.LINES:
            fields[name] = W.LinesField(label=fd["label"], required=False, help_text=fd["help"] or "One per line")
            fields[name].widget.attrs.update({"rows": 4, "class": "input"})
        elif t == HS.REP:
            spec_cols = [(k, lbl, "textarea" if "description" in k else "text") for k, lbl in fd["columns"]]
            fields[name] = W.RepeaterField(spec_cols, label=fd["label"], required=False, help_text=fd["help"])
        else:
            fields[name] = forms.CharField(label=fd["label"], required=False, help_text=fd["help"], max_length=600, widget=forms.TextInput(attrs={"class": "input"}))
    cls = type("SectionForm", (forms.Form,), fields)
    return cls(data, initial=initial, prefix=spec["key"])


def _ensure_sections():
    existing = {s.key: s for s in HomeSection.objects.all()}
    for i, spec in enumerate(HS.SECTIONS):
        if spec["key"] not in existing:
            existing[spec["key"]] = HomeSection.objects.create(key=spec["key"], label=spec["label"], order=i, is_visible=True)
    return existing


@needs("home", "view")
def home_builder(request):
    secs = _ensure_sections()
    ordered = sorted([s for s in secs.values() if s.key in HS.BY_KEY], key=lambda s: (0 if HS.BY_KEY[s.key].get("fixed_first") else 1, s.order))
    can_edit = request.user.can("home", "edit")
    posting = request.method == "POST"
    if posting and not can_edit:
        from .mixins import forbidden

        return forbidden(request)
    items, all_valid = [], True
    order_keys = request.POST.getlist("order") if posting else []
    if posting and order_keys:
        pos = {k: i for i, k in enumerate(order_keys)}
        ordered.sort(key=lambda s: (0 if HS.BY_KEY[s.key].get("fixed_first") else 1, pos.get(s.key, 99)))
    for sec in ordered:
        spec = HS.BY_KEY[sec.key]
        form = _section_form(spec, request.POST if posting else None, initial=HS.merged(sec))
        items.append({"sec": sec, "spec": spec, "form": form, "visible": (request.POST.get(f"visible-{sec.key}") == "on") if posting else sec.is_visible})
        if posting and not form.is_valid():
            all_valid = False
    if posting:
        reset = request.POST.get("reset")
        if reset in HS.BY_KEY:
            s = secs[reset]
            s.data = {}
            s.save()
            log_activity(request.user, "home.section_reset", s, "", request)
            messages.success(request, f"“{s.label}” restored to its default content.")
            return redirect("dashboard:home_builder")
        if all_valid:
            for i, it in enumerate(items):
                sec = it["sec"]
                sec.data = it["form"].cleaned_data
                sec.order = i
                sec.is_visible = True if it["spec"].get("fixed_first") else it["visible"]
                sec.save()
            log_activity(request.user, "home.updated", None, ", ".join(f"{it['sec'].key}{'' if it['visible'] else '(hidden)'}" for it in items)[:200], request)
            messages.success(request, "Home page saved. Changes are live on the website within a few moments.")
            return redirect("dashboard:home_builder")
        messages.error(request, "Some sections have errors. Please review them.")
    return render(request, "dashboard/home_builder.html", {"items": items, "can_edit": can_edit, "page_title": "Home page builder", "crumbs": [("Dashboard", "/dashboard/"), ("Home page builder", "")]})


# =================================================================== MEDIA LIBRARY
def _asset_json(a):
    return {"id": a.pk, "url": a.url, "title": str(a), "alt": a.alt_text, "kind": a.kind, "mime": a.mime_type, "size": a.size, "w": a.width, "h": a.height, "name": a.original_name}


MEDIA_SORTS = {
    "new": ("-created_at", "-id"), "old": ("created_at", "id"), "name": ("original_name", "title", "id"),
    "big": ("-size", "-id"), "small": ("size", "id"), "type": ("kind", "mime_type", "-created_at"),
}


def _media_qs(request):
    qs = MediaAsset.objects.select_related("uploaded_by")
    if request.GET.get("kind") in ("image", "document"):
        qs = qs.filter(kind=request.GET["kind"])
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(original_name__icontains=q) | Q(alt_text__icontains=q) | Q(file__icontains=q) | Q(caption__icontains=q))
    return qs.order_by(*MEDIA_SORTS.get(request.GET.get("sort", ""), MEDIA_SORTS["new"]))


@needs("media", "view")
def media_library(request):
    from django.conf import settings
    from django.db.models import Count, Sum

    per = request.GET.get("per")
    per = int(per) if per in ("24", "48", "96") else 24
    page = Paginator(_media_qs(request), per).get_page(request.GET.get("page"))
    qd = request.GET.copy()
    qd.pop("page", None)
    agg = MediaAsset.objects.aggregate(total=Count("id"), size=Sum("size"), images=Count("id", filter=Q(kind="image")), docs=Count("id", filter=Q(kind="document")))
    return render(request, "dashboard/media.html", {
        "page": page, "q": request.GET.get("q", ""), "kind": request.GET.get("kind", ""), "sort": request.GET.get("sort", "new"), "per": per, "qs": qd.urlencode(),
        "stats": {"total": agg["total"] or 0, "size": agg["size"] or 0, "images": agg["images"] or 0, "docs": agg["docs"] or 0},
        "max_mb": settings.MEDIA_MAX_UPLOAD_MB, "can_upload": request.user.can("media", "create"), "can_edit": request.user.can("media", "edit"), "can_delete": request.user.can("media", "delete"),
        "page_title": "Media library", "crumbs": [("Dashboard", "/dashboard/"), ("Media library", "")],
    })


@needs("media", "view")
def media_picker(request):
    page = Paginator(_media_qs(request), 18).get_page(request.GET.get("page"))
    return JsonResponse({"items": [_asset_json(a) for a in page.object_list], "page": page.number, "pages": page.paginator.num_pages})


def _any_media_upload_perm(request):
    return "media"


@needs("media", "create")
@require_POST
def media_upload(request):
    files = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not files:
        return JsonResponse({"error": {"message": "No file received."}}, status=400)
    out, errors = [], []
    for f in files[:20]:
        try:
            a = create_media_asset(f, request.user, alt_text=request.POST.get("alt", "")[:250])
            out.append(_asset_json(a))
            log_activity(request.user, "media.uploaded", a, f.name[:100], request)
        except ValidationError as exc:
            errors.append({"name": f.name, "message": "; ".join(exc.messages)})
        except Exception:
            errors.append({"name": f.name, "message": "Upload failed."})
    return JsonResponse({"items": out, "errors": errors}, status=200 if out else 400)


@needs("media", "edit")
@require_POST
def media_edit(request, pk):
    a = get_object_or_404(MediaAsset, pk=pk)
    a.title = request.POST.get("title", "")[:200]
    a.alt_text = request.POST.get("alt_text", "")[:250]
    a.caption = request.POST.get("caption", "")[:300]
    a.save(update_fields=["title", "alt_text", "caption", "updated_at"])
    log_activity(request.user, "media.updated", a, "", request)
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse(_asset_json(a))
    messages.success(request, "Media details saved.")
    return redirect("dashboard:media")


@needs("media", "view")
def media_download(request, pk):
    """Send the original file as a download (never rendered in the browser)."""
    from django.http import FileResponse, Http404

    a = get_object_or_404(MediaAsset, pk=pk)
    try:
        fh = a.file.open("rb")
    except (FileNotFoundError, ValueError, OSError):
        raise Http404("File is missing from storage.")
    log_activity(request.user, "media.downloaded", a, "", request)
    return FileResponse(fh, as_attachment=True, filename=a.download_name, content_type=a.mime_type or "application/octet-stream")


BULK_MAX_FILES, BULK_MAX_BYTES = 100, 300 * 1024 * 1024


@needs("media", "view")
@require_POST
def media_bulk(request):
    """Download several files as one ZIP, or delete several files that are not in use."""
    import tempfile
    import zipfile
    from django.http import FileResponse
    from django.utils import timezone

    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()][:BULK_MAX_FILES]
    action = request.POST.get("action")
    assets = list(MediaAsset.objects.filter(pk__in=ids))
    nxt = request.POST.get("next", "")
    back = nxt if nxt.startswith("/dashboard/media/") and "//" not in nxt else "/dashboard/media/"  # only ever back to this page
    if not assets:
        messages.error(request, "Select at least one file first.")
        return redirect(back)
    if action == "download":
        if sum(a.size for a in assets) > BULK_MAX_BYTES:
            messages.error(request, "Those files are too large for one ZIP (limit 300 MB). Select fewer files.")
            return redirect(back)
        tmp = tempfile.SpooledTemporaryFile(max_size=40 * 1024 * 1024)
        used = set()
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for a in assets:
                name = a.download_name
                if name in used:
                    root, ext = name.rsplit(".", 1) if "." in name else (name, "")
                    name = f"{root}-{a.pk}.{ext}" if ext else f"{root}-{a.pk}"
                used.add(name)
                try:
                    with a.file.open("rb") as fh:
                        z.writestr(name, fh.read())
                except (FileNotFoundError, OSError):
                    continue
        tmp.seek(0)
        log_activity(request.user, "media.downloaded", None, f"{len(assets)} files as ZIP", request)
        return FileResponse(tmp, as_attachment=True, filename=f"media-{timezone.now():%Y%m%d-%H%M}.zip", content_type="application/zip")
    if action == "delete":
        if not request.user.can("media", "delete"):
            return forbidden(request)
        in_use = media_used_ids(assets)
        deleted = 0
        for a in assets:
            if a.pk in in_use:
                continue
            a.file.delete(save=False)
            a.delete()
            deleted += 1
        skipped = len(in_use)
        log_activity(request.user, "media.deleted", None, f"{deleted} files (bulk), {skipped} skipped because they are in use", request)
        if deleted:
            messages.success(request, f"{deleted} file{'s' if deleted != 1 else ''} deleted." + (f" {skipped} still in use on the website and kept." if skipped else ""))
        else:
            messages.error(request, f"Nothing deleted: {skipped} file{'s are' if skipped != 1 else ' is'} still used on the website. Open a file to see where.")
        return redirect(back)
    messages.error(request, "Unknown action.")
    return redirect(back)


@needs("media", "view")
def media_usage_json(request, pk):
    a = get_object_or_404(MediaAsset, pk=pk)
    return JsonResponse({"usage": media_usage(a), "asset": _asset_json(a)})


@needs("media", "delete")
@require_POST
def media_delete(request, pk):
    a = get_object_or_404(MediaAsset, pk=pk)
    from apps.billing.models import CompanyDocument
    if CompanyDocument.objects.filter(asset=a).exists():
        messages.error(request, "This PDF is a saved version of your company profile (kept for the record). Choose a different profile under Billing → Company profile PDF; old versions are kept on purpose.")
        return redirect("dashboard:media")
    usage = media_usage(a)
    if usage and request.POST.get("force") != "1":
        places = "; ".join(f"{u['model']} “{u['object']}”" for u in usage[:4])
        messages.error(request, f"This file is still used in {len(usage)} place(s): {places}. Replace it there first, or confirm deletion anyway.")
        return redirect("dashboard:media")
    name = str(a)
    a.file.delete(save=False)
    a.delete()
    log_activity(request.user, "media.deleted", None, f"{name} (was used in {len(usage)} places)" if usage else name, request)
    messages.success(request, "File deleted.")
    return redirect("dashboard:media")
