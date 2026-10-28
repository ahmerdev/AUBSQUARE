"""Safe media uploads: type allow-list, size limit, magic-byte sniffing, Pillow verification, resizing."""
import io
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"}
MAX_DIMENSION = 2600


def _sniff_ok(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext in {".docx", ".xlsx", ".pptx"}:
        return head.startswith(b"PK")
    if ext in {".doc", ".xls", ".ppt"}:
        return head.startswith(b"\xd0\xcf\x11\xe0")
    if ext in {".txt", ".csv"}:
        return b"\x00" not in head
    return True


def process_upload(uploaded):
    """Validate an UploadedFile. Returns (ContentFile, kind, mime, width, height, size)."""
    name = os.path.basename(uploaded.name or "")
    ext = os.path.splitext(name)[1].lower()
    max_bytes = settings.MEDIA_MAX_UPLOAD_MB * 1024 * 1024
    if uploaded.size > max_bytes:
        raise ValidationError(f"File is too large (max {settings.MEDIA_MAX_UPLOAD_MB} MB).")
    if ext not in IMAGE_EXTS | DOC_EXTS:
        raise ValidationError("Unsupported file type. Allowed: JPG, PNG, WebP, GIF, PDF, DOC(X), XLS(X), PPT(X), TXT, CSV.")
    head = uploaded.read(2048)
    uploaded.seek(0)
    if not _sniff_ok(ext, head):
        raise ValidationError("The file content does not match its extension.")

    if ext in IMAGE_EXTS:
        try:
            img = Image.open(uploaded)
            img.verify()
            uploaded.seek(0)
            img = Image.open(uploaded)
            fmt = (img.format or "").upper()
        except Exception:
            raise ValidationError("This file is not a valid image.")
        if fmt not in {"JPEG", "PNG", "WEBP", "GIF"}:
            raise ValidationError("Unsupported image format.")
        mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}[fmt]
        if fmt == "GIF":  # keep animation untouched
            uploaded.seek(0)
            w, h = img.size
            return ContentFile(uploaded.read()), "image", mime, w, h, uploaded.size
        img = ImageOps.exif_transpose(img)  # strips orientation EXIF; other metadata dropped on re-save
        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        buf = io.BytesIO()
        if fmt == "JPEG":
            img.convert("RGB").save(buf, "JPEG", quality=86, optimize=True, progressive=True)
        elif fmt == "PNG":
            img.save(buf, "PNG", optimize=True)
        else:
            img.save(buf, "WEBP", quality=86, method=4)
        data = buf.getvalue()
        return ContentFile(data), "image", mime, img.size[0], img.size[1], len(data)

    mime = {
        ".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv",
    }.get(ext, "application/octet-stream")
    return ContentFile(uploaded.read()), "document", mime, None, None, uploaded.size


def create_media_asset(uploaded, user=None, title="", alt_text="", caption=""):
    from .models import MediaAsset

    content, kind, mime, w, h, size = process_upload(uploaded)
    asset = MediaAsset(
        title=title or os.path.splitext(os.path.basename(uploaded.name))[0][:200].replace("-", " ").replace("_", " "),
        alt_text=alt_text, caption=caption, kind=kind, mime_type=mime, size=size, width=w, height=h,
        original_name=os.path.basename(uploaded.name)[:200], uploaded_by=user,
    )
    asset.file.save(os.path.basename(uploaded.name), content, save=False)
    asset.save()
    return asset


def media_usage(asset):
    """Where is this file referenced? Scans every text/JSON field of the project's models."""
    from django.apps import apps
    from django.db import models as m
    from django.db.models.functions import Cast

    needle = asset.file.name  # uploads/2026/10/xxxx.jpg
    found = []
    for model in apps.get_models():
        if not model.__module__.startswith("apps.") or model is asset.__class__:
            continue
        for f in model._meta.get_fields():
            if not getattr(f, "concrete", False) or f.many_to_many or f.is_relation:
                continue
            if isinstance(f, (m.CharField, m.TextField)):
                qs = model.objects.filter(**{f"{f.name}__contains": needle})
            elif isinstance(f, m.JSONField):
                qs = model.objects.annotate(_t=Cast(f.name, m.TextField())).filter(_t__contains=needle)
            else:
                continue
            for obj in qs[:20]:
                found.append({"model": model._meta.verbose_name.title(), "object": str(obj)[:80], "field": f.verbose_name})
    return found


def media_used_ids(assets):
    """Primary keys of the given assets that are referenced somewhere (one query per text/JSON field, not one per file)."""
    from django.apps import apps
    from django.db import models as m
    from django.db.models.functions import Cast

    names = {a.file.name: a.pk for a in assets}
    if not names:
        return set()
    used = set()
    for model in apps.get_models():
        if not model.__module__.startswith("apps.") or model is assets[0].__class__:
            continue
        for f in model._meta.get_fields():
            if not getattr(f, "concrete", False) or f.many_to_many or f.is_relation:
                continue
            if isinstance(f, (m.CharField, m.TextField)):
                qs = model.objects.filter(_or_contains(f.name, names))
                col = f.name
            elif isinstance(f, m.JSONField):
                qs = model.objects.annotate(_t=Cast(f.name, m.TextField())).filter(_or_contains("_t", names))
                col = "_t"
            else:
                continue
            for text in qs.values_list(col, flat=True)[:2000]:
                text = text or ""
                for n, pk in names.items():
                    if pk not in used and n in text:
                        used.add(pk)
        if len(used) == len(names):
            break
    return used


def _or_contains(field, names):
    from django.db.models import Q

    q = Q()
    for n in names:
        q |= Q(**{f"{field}__contains": n})
    return q
