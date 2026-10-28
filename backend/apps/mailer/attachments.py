"""Email attachments are stored as small references and turned into real bytes only at send time, so a retry always attaches the file again.

Reference shapes:  {"kind": "media", "id": 12}  ·  {"kind": "invoice_pdf", "id": 5}  ·  {"kind": "receipt_pdf", "id": 9}
"""
MAX_TOTAL_BYTES = 15 * 1024 * 1024


class AttachmentError(Exception):
    pass


def resolve(ref: dict):
    """-> (filename, bytes, mimetype). Raises AttachmentError when the file is gone or not allowed."""
    kind = (ref or {}).get("kind")
    try:
        pk = int(ref.get("id"))
    except (TypeError, ValueError):
        raise AttachmentError("Invalid attachment reference.")
    if kind == "media":
        from apps.core.models import MediaAsset
        a = MediaAsset.objects.filter(pk=pk).first()
        if not a:
            raise AttachmentError("The attached file was removed from the Media library.")
        try:
            with a.file.open("rb") as fh:
                return a.download_name, fh.read(), a.mime_type or "application/octet-stream"
        except OSError:
            raise AttachmentError("The attached file could not be read from storage.")
    if kind == "invoice_pdf":
        from apps.billing.models import Invoice
        from apps.billing.pdf import invoice_pdf
        inv = Invoice.objects.filter(pk=pk).first()
        if not inv:
            raise AttachmentError("Invoice not found.")
        return f"Invoice-{inv.number or 'draft'}.pdf", invoice_pdf(inv), "application/pdf"
    if kind == "receipt_pdf":
        from apps.billing.models import Payment
        from apps.billing.pdf import receipt_pdf
        p = Payment.objects.select_related("invoice").filter(pk=pk, status="confirmed").first()
        if not p:
            raise AttachmentError("Receipt not found or the payment is not verified.")
        return f"Receipt-{p.receipt_number}.pdf", receipt_pdf(p), "application/pdf"
    raise AttachmentError("Unknown attachment type.")


def describe(refs):
    out, total = [], 0
    for r in refs or []:
        name, data, mime = resolve(r)
        total += len(data)
        out.append({"name": name, "size": len(data), "mime": mime})
    if total > MAX_TOTAL_BYTES:
        raise AttachmentError("The attachments are too large for email (limit 15 MB).")
    return out
