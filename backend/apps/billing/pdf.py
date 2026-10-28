"""Invoice and receipt PDFs (ReportLab). Layout rules: Paragraph cells so long text wraps, repeating table header, page X of Y on every page,
logo scaled by its real aspect ratio, DejaVu Sans bundled so ₨ € £ and accented names render on any server."""
import io
import os
from datetime import date
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import money

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_registered = False
W, H = A4
MARGIN = 18 * mm


def _fonts():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont("DJ", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DJ-B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ", boldItalic="DJ-B")
        _registered = True


def local_image_path(url: str):
    """Only files that live in our own MEDIA_ROOT are ever read – never remote URLs (no SSRF, no slow fetches)."""
    if not url:
        return None
    path = url
    if "://" in url:
        base = settings.SITE_URL.rstrip("/") + settings.MEDIA_URL
        if not url.startswith(base):
            return None
        path = settings.MEDIA_URL + url[len(base):]
    if not path.startswith(settings.MEDIA_URL):
        return None
    rel = os.path.normpath(path[len(settings.MEDIA_URL):].split("?")[0])
    full = os.path.abspath(os.path.join(settings.MEDIA_ROOT, rel))
    if not full.startswith(os.path.abspath(settings.MEDIA_ROOT) + os.sep) or not os.path.isfile(full):
        return None
    return full


def _logo(url, max_w=48 * mm, max_h=18 * mm):
    p = local_image_path(url)
    if not p:
        return None
    try:
        from PIL import Image as PI
        with PI.open(p) as im:
            im = im.convert("RGBA")
            w, h = im.size
            buf = io.BytesIO()
            im.save(buf, "PNG")
        ratio = min(max_w / w, max_h / h)
        buf.seek(0)
        return Image(buf, width=w * ratio, height=h * ratio, hAlign="LEFT")
    except Exception:  # noqa: BLE001 – a broken logo must never block an invoice
        return None


def _styles(brand):
    base = dict(fontName="DJ", fontSize=9, leading=12.5, textColor=colors.HexColor("#1b1830"))
    return {
        "n": ParagraphStyle("n", **base), "s": ParagraphStyle("s", **{**base, "fontSize": 8, "leading": 11, "textColor": colors.HexColor("#6b6784")}),
        "b": ParagraphStyle("b", **{**base, "fontName": "DJ-B"}), "r": ParagraphStyle("r", alignment=TA_RIGHT, **base),
        "rb": ParagraphStyle("rb", alignment=TA_RIGHT, **{**base, "fontName": "DJ-B"}), "h": ParagraphStyle("h", **{**base, "fontName": "DJ-B", "fontSize": 22, "leading": 26, "textColor": colors.HexColor(brand)}),
        "lbl": ParagraphStyle("lbl", **{**base, "fontName": "DJ-B", "fontSize": 7.5, "textColor": colors.HexColor("#6b6784")}),
        "th": ParagraphStyle("th", **{**base, "fontName": "DJ-B", "fontSize": 8, "textColor": colors.white}),
        "thr": ParagraphStyle("thr", alignment=TA_RIGHT, **{**base, "fontName": "DJ-B", "fontSize": 8, "textColor": colors.white}),
        "big": ParagraphStyle("big", alignment=TA_RIGHT, **{**base, "fontName": "DJ-B", "fontSize": 12, "leading": 15}),
    }


def _p(text, style):
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


class _Numbered(rl_canvas.Canvas):
    """Draws 'Page X of Y' and the optional status watermark on each page."""
    stamp = ""
    footer = ""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total):
        if self.stamp:
            self.saveState()
            self.setFont("DJ-B", 80)
            self.setFillColor(colors.Color(0.5, 0.5, 0.5, alpha=0.10))
            self.translate(W / 2, H / 2)
            self.rotate(35)
            self.drawCentredString(0, 0, self.stamp)
            self.restoreState()
        self.setFont("DJ", 7.5)
        self.setFillColor(colors.HexColor("#6b6784"))
        self.drawString(MARGIN, 10 * mm, self.footer[:110])
        self.drawRightString(W - MARGIN, 10 * mm, f"Page {self._pageNumber} of {total}")


def _build(story, title, footer, stamp=""):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm, bottomMargin=20 * mm, title=title, author="", creator="")

    class C(_Numbered):
        pass
    C.stamp, C.footer = stamp, footer
    doc.build(story, canvasmaker=C)
    return buf.getvalue()


def _header(co, label, number, st, brand):
    logo = _logo(co.get("logo"))
    left = [logo] if logo else [_p(co.get("trading_name") or co.get("name"), ParagraphStyle("nm", parent=st["h"], fontSize=16, leading=19))]
    right = [_p(label, st["h"]), _p(number, st["b"])]
    t = Table([[left, right]], colWidths=[(W - 2 * MARGIN) * 0.55, (W - 2 * MARGIN) * 0.45])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    for p in right:
        p.style = ParagraphStyle("x", parent=p.style, alignment=TA_RIGHT)
    return t


def _company_block(co, st):
    lines = [co.get("name") or ""]
    lines += co.get("address") or []
    for k in ("phone", "email", "website", "registration", "tax"):
        if co.get(k):
            lines.append(co[k])
    return [_p(lines[0], st["b"])] + [_p(x, st["s"]) for x in lines[1:]]


def _fmt(v, cur):
    return f"{money.q(v, cur):,.{money.decimals(cur)}f}"


def invoice_pdf(inv) -> bytes:
    _fonts()
    co = inv.company()
    brand = co.get("brand_color") or "#EC008C"
    if not (brand.startswith("#") and len(brand) in (4, 7)):
        brand = "#EC008C"
    st = _styles(brand)
    cur = inv.currency
    cw = W - 2 * MARGIN
    story = [_header(co, "INVOICE" if not inv.is_draft else "DRAFT INVOICE", inv.number or "Not yet issued", st, brand), Spacer(1, 5 * mm)]

    bill = [_p("BILL TO", st["lbl"]), _p(inv.client_company or inv.client_name, st["b"])]
    if inv.client_company and inv.client_name and inv.client_company.strip().lower() != inv.client_name.strip().lower():
        bill.append(_p(inv.client_name, st["n"]))
    for x in (inv.client_address, inv.client_country, inv.client_email, inv.client_phone, f"{inv.client_tax_label or 'Tax ID'}: {inv.client_tax_no}" if inv.client_tax_no else ""):
        if x:
            bill.append(_p(x, st["s"]))
    meta_rows = [("Issue date", inv.issue_date), ("Due date", inv.due_date), ("Status", inv.display_status_label), ("Currency", cur)]
    meta = Table([[_p(k, st["lbl"]), _p(v.strftime("%d %b %Y") if isinstance(v, date) else (v or "—"), st["rb"])] for k, v in meta_rows], colWidths=[26 * mm, 36 * mm])
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    two = Table([[_company_block(co, st), bill, meta]], colWidths=[cw * 0.36, cw * 0.34, cw * 0.30])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    story += [two, Spacer(1, 6 * mm)]
    if inv.project_name or inv.description:
        story.append(_p(inv.project_name, ParagraphStyle("pj", parent=st["b"], fontSize=11, leading=14)))
        if inv.description:
            story.append(_p(inv.description, st["n"]))
        story.append(Spacer(1, 3 * mm))

    rows = [[_p("DESCRIPTION", st["th"]), _p("QTY", st["thr"]), _p("UNIT PRICE", st["thr"]), _p("AMOUNT", st["thr"])]]
    for i in inv.items.all():
        desc = [_p(i.description, st["b"])] + ([_p(i.detail, st["s"])] if i.detail else [])
        qty = f"{i.quantity.normalize():f}" + (f" {i.unit}" if i.unit else "")
        rows.append([desc, _p(qty, st["r"]), _p(_fmt(i.unit_price, cur), st["r"]), _p(_fmt(i.total, cur), st["r"])])
    t = Table(rows, colWidths=[cw * 0.52, cw * 0.12, cw * 0.18, cw * 0.18], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand)), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d9d6e6")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf9fd")])]))
    story += [t, Spacer(1, 4 * mm)]

    tot = [("Subtotal", inv.subtotal)]
    if inv.discount:
        tot.append(("Discount", -inv.discount))
    if inv.tax_percent:
        tot.append((f"{inv.tax_name or 'Tax'} ({inv.tax_percent.normalize():f}%)", inv.tax_amount))
    trows = [[_p(k, st["n"]), _p(("-" if v < 0 else "") + _fmt(abs(v), cur), st["r"])] for k, v in tot]
    trows.append([_p(f"Total ({cur})", st["b"]), _p(_fmt(inv.total, cur), st["big"])])
    if inv.amount_paid:
        trows.append([_p("Amount paid", st["n"]), _p("-" + _fmt(inv.amount_paid, cur), st["r"])])
        trows.append([_p("Balance due", st["b"]), _p(_fmt(inv.balance, cur), st["big"])])
    tt = Table(trows, colWidths=[38 * mm, 38 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([("LINEABOVE", (0, len(tot)), (-1, len(tot)), 0.8, colors.HexColor(brand)), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(KeepTogether(tt))

    methods = inv.methods_snapshot or []
    if methods and inv.status not in (inv.CANCELLED, inv.VOID):
        story += [Spacer(1, 7 * mm), _p("HOW TO PAY", st["lbl"]), Spacer(1, 1.5 * mm)]
        cells = []
        for m in methods:
            lines = [_p(m.get("label"), st["b"])]
            for k, lab in (("account_title", "Account title"), ("bank_name", "Bank"), ("account_number", "Account no."), ("iban", "IBAN"), ("raast_id", "Raast ID"), ("swift_bic", "SWIFT/BIC"),
                           ("branch", "Branch"), ("bank_address", "Bank address"), ("correspondent_bank", "Intermediary bank")):
                if m.get(k):
                    lines.append(_p(f"{lab}: {m[k]}", st["s"]))
            if m.get("reference"):
                lines.append(_p(f"Payment reference: {m['reference']}", st["s"]))
            if m.get("link_url"):
                lines.append(_p(f"Payment link: {m['link_url']}", st["s"]))
            if m["kind"] == "stripe":
                lines.append(_p(f"Pay by card online: {settings.SITE_URL}{inv.public_path}", st["s"]))
            for extra in (m.get("instructions"), m.get("fee_note")):
                if extra:
                    lines.append(_p(extra, st["s"]))
            cells.append(lines)
        for a in range(0, len(cells), 2):
            row = cells[a:a + 2]
            if len(row) == 1:
                row.append([])
            bt = Table([row], colWidths=[cw / 2, cw / 2])
            bt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 0.4, colors.HexColor("#d9d6e6")), ("BOX", (1, 0), (1, 0), 0.4 if row[1] else 0, colors.HexColor("#d9d6e6")),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story += [KeepTogether(bt), Spacer(1, 2 * mm)]
    for title, text in (("PAYMENT TERMS", inv.terms), ("NOTES", inv.notes)):
        if text:
            story += [Spacer(1, 4 * mm), KeepTogether([_p(title, st["lbl"]), Spacer(1, 1 * mm), _p(text, st["s"])])]
    if co.get("signatory"):
        sig = _logo(co.get("signature"), 38 * mm, 14 * mm)
        story += [Spacer(1, 8 * mm), KeepTogether([x for x in (sig, _p(co["signatory"], st["b"]), _p(co.get("signatory_title", ""), st["s"])) if x])]
    foot = inv.footer or co.get("footer") or ""
    if foot:
        story += [Spacer(1, 6 * mm), _p(foot, st["s"])]
    stamp = {"paid": "PAID", "void": "VOID", "cancelled": "CANCELLED", "draft": "DRAFT"}.get(inv.status, "")
    name = co.get("trading_name") or co.get("name") or ""
    return _build(story, f"Invoice {inv.number or 'draft'}", f"{name}  ·  {inv.number or 'Draft'}", stamp)


def receipt_pdf(p) -> bytes:
    _fonts()
    inv = p.invoice
    co = inv.company()
    brand = co.get("brand_color") or "#EC008C"
    st = _styles(brand)
    cw = W - 2 * MARGIN
    cur = p.currency
    story = [_header(co, "RECEIPT", p.receipt_number or "Unverified", st, brand), Spacer(1, 5 * mm)]
    left = _company_block(co, st)
    right = [_p("RECEIVED FROM", st["lbl"]), _p(inv.client_company or inv.client_name, st["b"])] + [_p(x, st["s"]) for x in (inv.client_name if inv.client_company and inv.client_company.strip().lower() != inv.client_name.strip().lower() else "", inv.client_email, inv.client_address) if x]
    two = Table([[left, right]], colWidths=[cw * 0.5, cw * 0.5])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [two, Spacer(1, 8 * mm)]
    rows = [("Invoice", inv.number), ("Project", inv.project_name), ("Payment date", (p.paid_on or p.created_at).strftime("%d %b %Y")), ("Payment method", p.method_label or "—"),
            ("Transaction reference", p.reference or p.provider_txn_id or "—"), ("Amount credited to invoice", money.fmt(p.amount, cur))]
    if p.received_currency:
        rows.insert(5, ("Amount received", f"{p.received_currency} {_fmt(p.received_amount or 0, p.received_currency)}" + (f"  @ rate {p.exchange_rate.normalize():f}" if p.exchange_rate else "")))
        if p.bank_fee:
            rows.insert(6, ("Bank fees recorded", f"{p.received_currency} {_fmt(p.bank_fee, p.received_currency)}"))
    rows += [("Invoice total", money.fmt(inv.total, cur)), ("Total paid to date", money.fmt(inv.amount_paid, cur)), ("Remaining balance", money.fmt(inv.balance, cur)),
             ("Verification", "Verified" + (f" on {timezone.localtime(p.verified_at):%d %b %Y}" if p.verified_at else "") if p.status == p.CONFIRMED else p.get_status_display())]
    rows = [r for r in rows if r[1]]
    t = Table([[_p(k, st["lbl"]), _p(v, st["b"])] for k, v in rows], colWidths=[cw * 0.4, cw * 0.6])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d6e6")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 10 * mm), _p("Thank you for your payment. This receipt confirms the payment above was verified and applied to the invoice.", st["s"])]
    if co.get("email") or co.get("phone"):
        story.append(_p("Questions? " + " · ".join(x for x in (co.get("email"), co.get("phone")) if x), st["s"]))
    name = co.get("trading_name") or co.get("name") or ""
    return _build(story, f"Receipt {p.receipt_number}", f"{name}  ·  Receipt {p.receipt_number or ''}", "REFUNDED" if p.refunded_amount >= p.amount else "")
