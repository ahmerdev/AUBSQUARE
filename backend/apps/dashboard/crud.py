"""Generic, registry-driven list / create / edit / delete / bulk / export views."""
import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.core.paginator import Paginator
from django.db import models, router
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.services import log_activity
from apps.seo import resolver
from . import registry
from .forms import bound_fieldsets, make_form
from .mixins import forbidden, needs

PAGE_SIZE = 20


def _module(slug):
    m = registry.get(slug)
    if not m:
        raise Http404
    return m


def _perm_mod(request, mslug, *a, **k):
    return _module(mslug).perm


def _base_qs(m):
    qs = m.Model.objects.all()
    if m.slug == "posts":
        qs = qs.select_related("category").annotate(comment_count=Count("comments", distinct=True))
    else:
        rels = [f.name for f in m.Model._meta.get_fields() if f.is_relation and f.many_to_one and f.name in {c[0] for c in m.columns}]
        if rels:
            qs = qs.select_related(*rels)
    return qs


def _value(obj, attr):
    v = getattr(obj, attr, "")
    if callable(v):
        v = v()
    return v


def _cell(obj, col):
    attr, label, kind = col
    v = _value(obj, attr)
    display = v
    f = None
    try:
        f = obj._meta.get_field(attr)
    except Exception:
        pass
    if f is not None and getattr(f, "choices", None):
        display = getattr(obj, f"get_{attr}_display")()
    if v is None:
        display = ""
    return {"kind": kind, "value": v, "display": display, "attr": attr}


def _filter_defs(m, request):
    defs = []
    for name in m.filters:
        f = m.Model._meta.get_field(name)
        cur = request.GET.get(name, "")
        if getattr(f, "choices", None):
            opts = [(str(k), str(lbl)) for k, lbl in f.choices]
        elif isinstance(f, models.BooleanField):
            opts = [("1", "Yes"), ("0", "No")]
        elif f.is_relation:
            opts = [(str(o.pk), str(o)) for o in f.related_model.objects.all()[:200]]
        else:
            vals = m.Model.objects.exclude(**{name: ""}).order_by(name).values_list(name, flat=True).distinct()[:100]
            opts = [(str(v), str(v)) for v in vals if v]
        defs.append({"name": name, "label": str(f.verbose_name).capitalize(), "options": opts, "current": cur})
    return defs


def apply_filters(m, request, qs):
    q = request.GET.get("q", "").strip()
    if q and m.search:
        cond = Q()
        for s in m.search:
            cond |= Q(**{f"{s}__icontains": q})
        qs = qs.filter(cond)
    for name in m.filters:
        val = request.GET.get(name, "")
        if val == "":
            continue
        f = m.Model._meta.get_field(name)
        if isinstance(f, models.BooleanField):
            qs = qs.filter(**{name: val == "1"})
        else:
            qs = qs.filter(**{name: val})
    return qs


def _crumbs(m, last=""):
    c = [("Dashboard", reverse("dashboard:home"))]
    if m.parent:
        c.append((m.parent, ""))
    c.append((m.title, reverse("dashboard:list", args=[m.slug]) if last else ""))
    if last:
        c.append((last, ""))
    return c


@needs(_perm_mod, "view")
def list_view(request, mslug):
    m = _module(mslug)
    if m.singleton:
        return redirect("dashboard:edit", mslug=mslug, pk=1)
    qs = apply_filters(m, request, _base_qs(m))
    sort = request.GET.get("sort", "")
    allowed = {c[0] for c in m.columns}
    if sort.lstrip("-") in allowed and not callable(getattr(m.Model, sort.lstrip("-"), None)):
        qs = qs.order_by(sort)
    elif m.ordering:
        qs = qs.order_by(*m.ordering)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    rows = []
    for obj in page.object_list:
        rows.append({
            "obj": obj, "pk": obj.pk, "cells": [_cell(obj, c) for c in m.columns],
            "edit_url": reverse("dashboard:edit", args=[m.slug, obj.pk]),
            "detail_url": reverse("dashboard:campaign_detail", args=[obj.pk]) if m.slug == "campaigns" else reverse("dashboard:detail", args=[m.slug, obj.pk]),
            "view_url": m.preview(obj) if m.preview and getattr(obj, "is_live", True) else "",
        })
    qd = request.GET.copy()
    qd.pop("page", None)
    ctx = {
        "m": m, "rows": rows, "page": page, "filters": _filter_defs(m, request), "q": request.GET.get("q", ""), "qs": qd.urlencode(),
        "can_create": m.can_create and request.user.can(m.perm, "create"), "can_delete": m.can_delete and request.user.can(m.perm, "delete"),
        "can_export": bool(m.export) and request.user.can(m.perm, "export"), "can_edit": request.user.can(m.perm, "edit"),
        "bulk": [b for b in m.bulk if request.user.can(m.perm, b[2])], "total": page.paginator.count,
        "has_filters": any(request.GET.get(f["name"]) for f in _filter_defs(m, request)) or bool(request.GET.get("q")),
        "page_title": m.title, "crumbs": _crumbs(m), "columns": m.columns, "sort": sort,
    }
    return render(request, m.list_template or "dashboard/crud_list.html", ctx)


def _preview_url(m, obj):
    if not m.preview or not obj.pk:
        return ""
    path = m.preview(obj)
    parts = path.strip("/").split("/")
    if len(parts) == 2 and getattr(obj, "slug", None):
        return f"{path}?preview={resolver.preview_token(parts[0], obj.slug)}"
    return path


def _seo_base(m, obj):
    """Prefix shown in the search-result preview, e.g. https://site.com/blog/"""
    from django.conf import settings

    if m.singleton or not m.preview or "seo_title" not in m.form_fields:
        return ""
    sample = m.preview(obj) if obj.pk else m.preview(type("O", (), {"slug": "x", "path": "/"})())
    return settings.SITE_URL + (sample.rsplit("/", 1)[0] + "/" if sample.strip("/").count("/") >= 1 else "/")


def _form_view(request, m, obj):
    Form = make_form(m, request.user)
    creating = obj.pk is None
    needed = "create" if creating else "edit"
    if not request.user.can(m.perm, needed):
        return forbidden(request)
    initial = dict(m.defaults)
    if creating and m.slug == "posts":
        initial["author"] = request.user
    form = Form(request.POST or None, request.FILES or None, instance=obj, initial=initial)
    if request.method == "POST" and form.is_valid():
        changed = [f for f in form.changed_data if not f.endswith("_clear")]
        saved = form.save()
        if creating and m.slug == "posts" and not saved.author_id:
            saved.author = request.user
            saved.save(update_fields=["author"])
        log_activity(request.user, f"{m.slug}.{'created' if creating else 'updated'}", saved, ", ".join(changed)[:200] if not creating else "", request)
        messages.success(request, f"{m.singular.capitalize()} {'created' if creating else 'saved'}.")
        if request.POST.get("_continue") or m.singleton:
            return redirect("dashboard:edit", mslug=m.slug, pk=saved.pk)
        return redirect("dashboard:list", mslug=m.slug)
    elif request.method == "POST":
        messages.error(request, "Please fix the highlighted fields and try again.")
    ctx = {
        "m": m, "form": form, "obj": obj, "creating": creating, "fieldsets": bound_fieldsets(form, m),
        "page_title": f"New {m.singular}" if creating else (f"Edit {m.singular}" if not m.singleton else m.title),
        "crumbs": _crumbs(m, f"New {m.singular}" if creating else (str(obj)[:40] if not m.singleton else "")),
        "preview_url": _preview_url(m, obj) if not creating else "", "live": getattr(obj, "is_live", None),
        "can_delete": m.can_delete and not creating and request.user.can(m.perm, "delete"),
        "has_richtext": "rich" in m.types.values(), "seo_base": _seo_base(m, obj),
    }
    return render(request, m.form_template or "dashboard/crud_form.html", ctx)


# ------------------------------------------------------------------ read-only "View details" page
_HIDDEN_FIELD_HINTS = ("password", "secret", "token", "api_key", "_enc", "credential")
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")


def _is_image_url(v):
    return isinstance(v, str) and (v.split("?")[0].lower().endswith(_IMG_EXT))


def _detail_item(m, obj, name):
    """One labelled value for the details page. Secrets are never shown, and only real model fields are read."""
    if any(h in name for h in _HIDDEN_FIELD_HINTS):
        return None
    try:
        f = obj._meta.get_field(name)
    except Exception:
        return None
    label = str(getattr(f, "verbose_name", name)).capitalize()
    t = m.types.get(name)
    item = {"label": label, "name": name, "kind": "text", "value": None, "help": getattr(f, "help_text", "")}
    if f.many_to_many:
        item.update(kind="chips", value=[str(o) for o in getattr(obj, name).all()])
        return item
    v = getattr(obj, name, None)
    if f.is_relation:
        rel = v
        item.update(kind="text", value=str(rel) if rel is not None else "")
        return item
    if isinstance(f, models.BooleanField):
        item.update(kind="bool", value=bool(v))
    elif getattr(f, "choices", None):
        item.update(kind="badge", value=v, display=getattr(obj, f"get_{name}_display")() if v not in (None, "") else "")
    elif isinstance(f, models.JSONField):
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            keys = []
            for x in v:
                for k in x:
                    if k not in keys:
                        keys.append(k)
            item.update(kind="table", value={"keys": [k.replace("_", " ").capitalize() for k in keys], "rows": [[str(x.get(k, "")) for k in keys] for x in v]})
        elif isinstance(v, list):
            item.update(kind="chips" if all(isinstance(x, (str, int, float)) for x in v) else "json", value=[str(x) for x in v] if all(isinstance(x, (str, int, float)) for x in v) else v)
        else:
            item.update(kind="json", value=v if v else None)
        if item["kind"] == "json" and item["value"] is not None:
            import json as _json

            item["value"] = _json.dumps(item["value"], indent=2, ensure_ascii=False)
    elif t == "rich":
        from apps.core.sanitize import clean_html

        item.update(kind="rich", value=clean_html(v or ""))
    elif name.endswith("_color") or (isinstance(v, str) and v.startswith("#") and len(v) in (4, 7, 9) and "color" in name):
        item.update(kind="color", value=v)
    elif t == "media" or _is_image_url(v) or (isinstance(f, models.CharField) and any(h in name for h in ("image", "logo", "favicon", "avatar", "thumbnail", "photo")) and "alt" not in name and v):
        item.update(kind="image" if _is_image_url(v) or (isinstance(v, str) and "/media/" in v) else "text", value=v)
    elif isinstance(f, (models.DateTimeField,)):
        item.update(kind="datetime", value=v)
    elif isinstance(f, models.DateField):
        item.update(kind="date", value=v)
    elif isinstance(f, models.URLField) or (isinstance(v, str) and v.startswith(("http://", "https://"))):
        item.update(kind="url", value=v)
    elif isinstance(f, models.TextField):
        item.update(kind="long", value=v)
    else:
        item.update(value=v)
    return item


@needs(_perm_mod, "view")
def detail_view(request, mslug, pk):
    m = _module(mslug)
    if m.singleton:
        return redirect("dashboard:edit", mslug=mslug, pk=1)
    obj = get_object_or_404(m.Model, pk=pk)
    sections = []
    for title, names in m.fieldsets:
        items = [i for i in (_detail_item(m, obj, n) for n in names) if i]
        if items:
            sections.append({"title": title, "items": items})
    hero_img = ""
    for col in m.columns:
        if col[2] == "image" and getattr(obj, col[0], ""):
            hero_img = getattr(obj, col[0])
            break
    status_val = getattr(obj, m.status_field, "") if m.status_field else ""
    meta = [("ID", f"#{obj.pk}")]
    for attr, label in (("created_at", "Created"), ("updated_at", "Last updated"), ("published_at", "Published")):
        if getattr(obj, attr, None):
            meta.append((label, getattr(obj, attr)))
    if getattr(obj, "author", None):
        meta.append(("Author", str(obj.author)))
    ctx = {
        "m": m, "obj": obj, "sections": sections, "hero_img": hero_img, "meta": meta,
        "status_val": status_val, "status_display": getattr(obj, f"get_{m.status_field}_display")() if status_val else "",
        "live": getattr(obj, "is_live", None), "preview_url": _preview_url(m, obj),
        "can_edit": request.user.can(m.perm, "edit"), "can_delete": m.can_delete and request.user.can(m.perm, "delete") and not getattr(obj, "is_system", False),
        "page_title": str(obj)[:60], "crumbs": _crumbs(m, str(obj)[:40]),
        "prev_next": _neighbours(m, obj),
    }
    return render(request, "dashboard/crud_detail.html", ctx)


def _neighbours(m, obj):
    """Previous / next record in the module's default ordering (so people can page through details)."""
    try:
        ids = list(m.Model.objects.order_by(*(m.ordering or ["pk"])).values_list("pk", flat=True)[:1000])
        i = ids.index(obj.pk)
    except Exception:
        return {}
    return {"prev": ids[i - 1] if i > 0 else None, "next": ids[i + 1] if i + 1 < len(ids) else None, "pos": i + 1, "total": len(ids)}


@needs(_perm_mod, "create")
@require_http_methods(["GET", "POST"])
def create_view(request, mslug):
    m = _module(mslug)
    if not m.can_create:
        raise Http404
    return _form_view(request, m, m.Model())


@needs(_perm_mod, "view")
@require_http_methods(["GET", "POST"])
def edit_view(request, mslug, pk):
    m = _module(mslug)
    obj = m.Model.load() if m.singleton else get_object_or_404(m.Model, pk=pk)
    return _form_view(request, m, obj)


@needs(_perm_mod, "delete")
@require_http_methods(["GET", "POST"])
def delete_view(request, mslug, pk):
    m = _module(mslug)
    if not m.can_delete:
        raise Http404
    obj = get_object_or_404(m.Model, pk=pk)
    using = router.db_for_write(m.Model)
    collector = NestedObjects(using=using)
    collector.collect([obj])
    related = [str(o) for o in collector.nested() if False] if False else _flatten(collector.nested(), obj)
    protected = list(collector.protected)
    if getattr(obj, "is_system", False):
        messages.error(request, "Built-in items can't be deleted.")
        return redirect("dashboard:list", mslug=m.slug)
    if request.method == "POST":
        if protected:
            messages.error(request, "This item is protected by related records and can't be deleted.")
            return redirect("dashboard:edit", mslug=m.slug, pk=pk)
        label = str(obj)
        log_activity(request.user, f"{m.slug}.deleted", obj, label[:200], request)
        obj.delete()
        messages.success(request, f"{m.singular.capitalize()} deleted.")
        return redirect("dashboard:list", mslug=m.slug)
    return render(request, "dashboard/confirm_delete.html", {"m": m, "obj": obj, "related": related, "protected": protected, "page_title": f"Delete {m.singular}", "crumbs": _crumbs(m, "Delete")})


def _flatten(nested, root):
    out = []

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
            elif it is not root:
                out.append(f"{it._meta.verbose_name.capitalize()}: {it}")

    walk(nested)
    return out[:30]


def _csv_safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@needs(_perm_mod, "export")
def export_view(request, mslug):
    m = _module(mslug)
    if not m.export:
        raise Http404
    qs = apply_filters(m, request, _base_qs(m)).order_by(*(m.ordering or ["pk"]))
    ids = request.GET.get("ids")
    if ids:
        qs = qs.filter(pk__in=[i for i in ids.split(",") if i.isdigit()])
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{m.slug}-{datetime.now():%Y%m%d-%H%M}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(m.export)
    for o in qs.iterator():
        w.writerow([_csv_safe(_value(o, f)) for f in m.export])
    log_activity(request.user, f"{m.slug}.exported", None, f"{qs.count()} rows", request)
    return resp


@needs(_perm_mod, "view")
@require_POST
def bulk_view(request, mslug):
    m = _module(mslug)
    action = request.POST.get("action", "")
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()]
    spec = next((b for b in m.bulk if b[0] == action), None)
    if not spec or not ids:
        messages.error(request, "Choose at least one item and an action.")
        return redirect("dashboard:list", mslug=m.slug)
    if not request.user.can(m.perm, spec[2]):
        return forbidden(request)
    qs = m.Model.objects.filter(pk__in=ids)
    count = 0
    for obj in qs:
        if action == "delete":
            if not m.can_delete or getattr(obj, "is_system", False):
                continue
            log_activity(request.user, f"{m.slug}.deleted", obj, str(obj)[:200], request)
            obj.delete()
        elif action in ("publish", "draft") and m.status_field:
            obj.status = "published" if action == "publish" else "draft"
            obj.save()
        elif action in ("show", "hide"):
            obj.is_published = action == "show"
            obj.save()
        else:
            continue
        count += 1
    if action != "delete" and count:
        log_activity(request.user, f"{m.slug}.bulk_{action}", None, f"{count} items", request)
    messages.success(request, f"{count} item{'s' if count != 1 else ''} updated.")
    return redirect(request.POST.get("next") or reverse("dashboard:list", args=[m.slug]))
