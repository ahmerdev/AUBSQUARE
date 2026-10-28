"""Billing: company details, invoices, payments, receipts, refunds, gateway events and audit trail.

Rules baked into the data model:
* money is Decimal everywhere and stays in the invoice's own currency;
* an issued invoice keeps a snapshot of the company details, so later settings changes never rewrite history;
* a payment only counts toward an invoice once it is *confirmed*;
* the same provider transaction can never be stored twice (unique constraint).
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import SingletonModel, TimeStamped
from . import money

ZERO = Decimal("0.00")


def new_token(n=28):
    return secrets.token_urlsafe(n)[:n + 4]


# ------------------------------------------------------------------ company settings
class CompanyBilling(SingletonModel, TimeStamped):
    legal_name = models.CharField(max_length=200, blank=True)
    trading_name = models.CharField(max_length=200, blank=True, help_text="If different from the legal name. Shown on documents when set.")
    logo_url = models.CharField(max_length=500, blank=True, help_text="Pick from the Media library. Leave empty to use the website logo.")
    address_line1 = models.CharField("Address line 1", max_length=200, blank=True)
    address_line2 = models.CharField("Address line 2", max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=80, blank=True, default="Pakistan")
    phone = models.CharField("Business phone", max_length=40, blank=True)
    email = models.EmailField("Business email", blank=True)
    website = models.URLField("Website URL", blank=True)
    registration_label = models.CharField("Registration label", max_length=40, blank=True, default="Company reg. no.", help_text="e.g. SECP reg. no., Companies House no.")
    registration_no = models.CharField("Company registration number", max_length=60, blank=True)
    tax_label = models.CharField("Tax registration label", max_length=40, blank=True, default="NTN", help_text="e.g. NTN, STRN, VAT no., GST no., EIN. Leave empty if you have none.")
    tax_no = models.CharField("Tax registration number", max_length=60, blank=True)
    tax_name = models.CharField("Name of the tax on invoices", max_length=30, default="Tax", help_text="e.g. Sales tax, VAT, GST. Only used when a tax rate is applied.")
    default_tax_percent = models.DecimalField("Default tax rate (%)", max_digits=5, decimal_places=2, default=0, help_text="0 = no tax is added unless you set it on an invoice.")
    default_currency = models.CharField("Default invoice currency", max_length=3, default="USD")
    quotation_currency = models.CharField("Default quotation currency", max_length=3, default="USD")
    enabled_currencies = models.CharField(max_length=120, default=money.DEFAULT_ENABLED, help_text="Comma separated, e.g. USD,PKR,GBP,EUR,AED,SAR,CAD")
    payment_terms_days = models.PositiveSmallIntegerField("Default payment terms (days)", default=14)
    invoice_prefix = models.CharField(max_length=12, default="INV", help_text="Invoices are numbered PREFIX-YEAR-0001.")
    invoice_start_number = models.PositiveIntegerField("Next invoice number at least", default=1, help_text="Raise this to continue an existing numbering sequence. It can never reuse a number.")
    number_padding = models.PositiveSmallIntegerField(default=4)
    reset_numbering_yearly = models.BooleanField(default=True)
    receipt_prefix = models.CharField(max_length=12, default="RCT")
    invoice_footer = models.TextField(blank=True, help_text="Printed at the bottom of every invoice (thank-you line, late-fee policy, legal text).")
    payment_instructions = models.TextField(blank=True, help_text="General instructions printed with the payment details.")
    default_notes = models.TextField(blank=True)
    signatory_name = models.CharField("Authorised signatory", max_length=120, blank=True)
    signatory_title = models.CharField(max_length=120, blank=True)
    signature_url = models.CharField("Signature image", max_length=500, blank=True)
    brand_color = models.CharField(max_length=9, default="#EC008C")
    send_reminders = models.BooleanField("Send automatic payment reminders", default=False, help_text="Off by default. Reminders are never sent for paid, cancelled, void or disputed invoices.")
    remind_before_days = models.PositiveSmallIntegerField("Remind this many days before due", default=3)
    remind_every_days = models.PositiveSmallIntegerField("Repeat overdue reminders every (days)", default=7)
    max_reminders = models.PositiveSmallIntegerField(default=3)

    class Meta:
        verbose_name = "Company billing settings"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.trading_name or self.legal_name or "Your company"

    @property
    def currency_list(self):
        out = [c.strip().upper() for c in (self.enabled_currencies or "").split(",") if c.strip().upper() in money.CURRENCIES]
        return out or ["USD"]

    @property
    def address_lines(self):
        city = " ".join(x for x in (self.postal_code, self.city) if x)
        return [x for x in (self.address_line1, self.address_line2, city, self.country) if x]

    def logo(self):
        if self.logo_url:
            return self.logo_url
        from apps.core.models import SiteSettings
        return SiteSettings.load().logo_url

    def snapshot(self) -> dict:
        return {
            "name": self.legal_name or self.display_name, "trading_name": self.trading_name, "logo": self.logo(), "address": self.address_lines,
            "phone": self.phone, "email": self.email, "website": self.website, "registration": f"{self.registration_label}: {self.registration_no}" if self.registration_no else "",
            "tax": f"{self.tax_label}: {self.tax_no}" if self.tax_no else "", "footer": self.invoice_footer, "brand_color": self.brand_color,
            "signatory": self.signatory_name, "signatory_title": self.signatory_title, "signature": self.signature_url,
        }


class NumberSequence(models.Model):
    """One counter per key (e.g. invoice-2026). Always read with select_for_update inside a transaction."""
    key = models.CharField(max_length=40, unique=True)
    last = models.PositiveIntegerField(default=0)

    @classmethod
    def take(cls, key: str, at_least: int = 1) -> int:
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(key=key)
            seq.last = max(seq.last + 1, at_least)
            seq.save(update_fields=["last"])
            return seq.last


# ------------------------------------------------------------------ payment methods & gateways
class PaymentMethod(TimeStamped):
    BANK_PK, IBFT, RAAST, WIRE, STRIPE, PAYPAL, PAYONEER, LINK, OTHER = "bank_pk", "ibft", "raast", "wire", "stripe", "paypal", "payoneer", "link", "other"
    KINDS = [(BANK_PK, "Bank transfer (Pakistan)"), (IBFT, "IBFT (inter-bank fund transfer)"), (RAAST, "Raast"), (WIRE, "International wire (SWIFT)"),
             (STRIPE, "Stripe (hosted card checkout)"), (PAYPAL, "PayPal (payment link you create)"), (PAYONEER, "Payoneer (payment request you create)"),
             (LINK, "Other payment link"), (OTHER, "Other / cash")]
    OFFLINE = (BANK_PK, IBFT, RAAST, WIRE, PAYPAL, PAYONEER, LINK, OTHER)  # confirmed by staff after checking real records
    BANK_LIKE = (BANK_PK, IBFT, RAAST, WIRE)
    kind = models.CharField(max_length=10, choices=KINDS, db_index=True)
    label = models.CharField(max_length=80, help_text="What the client sees, e.g. 'Bank transfer (PKR)'.")
    is_enabled = models.BooleanField(default=False)
    currencies = models.CharField(max_length=80, blank=True, help_text="Comma separated currencies this method accepts. Empty = all enabled currencies.")
    sort_order = models.PositiveSmallIntegerField(default=0)
    account_title = models.CharField(max_length=150, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=60, blank=True)
    iban = models.CharField("IBAN", max_length=40, blank=True)
    branch = models.CharField("Branch details", max_length=200, blank=True)
    raast_id = models.CharField("Raast ID / alias", max_length=80, blank=True)
    swift_bic = models.CharField("SWIFT / BIC", max_length=20, blank=True)
    bank_address = models.CharField(max_length=250, blank=True)
    correspondent_bank = models.CharField("Correspondent / intermediary bank", max_length=250, blank=True)
    reference_format = models.CharField(max_length=80, default="{invoice}", help_text="What the client must write as the transfer reference. {invoice} = invoice number.")
    instructions = models.TextField(blank=True, help_text="Shown to the client with the details above.")
    fee_note = models.CharField("Fees note", max_length=250, blank=True, help_text="e.g. 'Intermediary bank fees and exchange-rate differences may reduce the amount we receive.'")
    link_url = models.URLField("Payment link / page", blank=True, help_text="Only for PayPal / Payoneer / other link methods: a real page you have created in your provider account.")
    mode = models.CharField(max_length=5, default="test", choices=[("test", "Test / sandbox"), ("live", "Live")], help_text="Gateways only. Keep on Test until you have completed a sandbox payment end to end.")
    verified_eligible = models.BooleanField("I have confirmed this provider is available to my business", default=False, help_text="Tick only after your provider account is approved. Online gateways stay switched off until then.")
    notes = models.TextField(blank=True, help_text="Internal note (eligibility checks, account manager...). Never shown to clients.")

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.label

    @property
    def is_gateway(self):
        return self.kind == self.STRIPE

    @property
    def needs_verification(self):
        return self.kind in self.OFFLINE

    def accepts(self, currency: str) -> bool:
        lst = [c.strip().upper() for c in self.currencies.split(",") if c.strip()]
        return not lst or currency.upper() in lst

    def reference_for(self, invoice) -> str:
        try:
            return (self.reference_format or "{invoice}").format(invoice=invoice.number or "", client=invoice.client_name[:20])
        except (KeyError, IndexError, ValueError):
            return invoice.number or ""

    @property
    def gateway_ready(self):
        if not self.is_gateway:
            return True
        from .gateways import get_gateway
        g = get_gateway(self)
        return bool(g and g.configured())

    def snapshot_for(self, invoice) -> dict:
        d = {"id": self.pk, "kind": self.kind, "label": self.label, "reference": self.reference_for(invoice), "instructions": self.instructions, "fee_note": self.fee_note}
        if self.kind in self.BANK_LIKE:
            d.update(account_title=self.account_title, bank_name=self.bank_name, account_number=self.account_number, iban=self.iban, branch=self.branch,
                     raast_id=self.raast_id, swift_bic=self.swift_bic, bank_address=self.bank_address, correspondent_bank=self.correspondent_bank)
        if self.link_url and self.kind in (self.PAYPAL, self.PAYONEER, self.LINK):
            d["link_url"] = self.link_url
        return d


# ------------------------------------------------------------------ invoices
class Invoice(TimeStamped):
    DRAFT, ISSUED, SENT, PARTIAL, PAID, CANCELLED, VOID = "draft", "issued", "sent", "partially_paid", "paid", "cancelled", "void"
    STATUS = [(DRAFT, "Draft"), (ISSUED, "Issued"), (SENT, "Sent"), (PARTIAL, "Partially paid"), (PAID, "Paid"), (CANCELLED, "Cancelled"), (VOID, "Void")]
    OPEN = (ISSUED, SENT, PARTIAL)
    FULL, DEPOSIT, FINAL, MILESTONE, HOURLY, RECURRING = "full", "deposit", "final", "milestone", "hourly", "recurring"
    BILLING_TYPES = [(FULL, "Full payment"), (DEPOSIT, "Deposit"), (FINAL, "Final payment"), (MILESTONE, "Milestone"), (HOURLY, "Hourly / time-based"), (RECURRING, "Recurring (manual cycle)")]

    number = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    token = models.CharField(max_length=40, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=STATUS, default=DRAFT, db_index=True)
    billing_type = models.CharField(max_length=10, choices=BILLING_TYPES, default=FULL)
    milestone_label = models.CharField(max_length=120, blank=True)
    client_name = models.CharField(max_length=160)
    client_company = models.CharField(max_length=160, blank=True)
    client_email = models.EmailField(blank=True)
    client_phone = models.CharField(max_length=40, blank=True)
    client_address = models.TextField(blank=True)
    client_country = models.CharField(max_length=80, blank=True)
    client_tax_label = models.CharField(max_length=40, blank=True)
    client_tax_no = models.CharField(max_length=60, blank=True)
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    prospect = models.ForeignKey("outbound.Prospect", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    proposal = models.ForeignKey("outbound.Proposal", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    replaces = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="revisions")
    project_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="USD")
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_name = models.CharField(max_length=30, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    footer = models.TextField(blank=True)
    methods = models.ManyToManyField(PaymentMethod, blank=True, related_name="invoices")
    company_snapshot = models.JSONField(default=dict, blank=True)
    methods_snapshot = models.JSONField(default=list, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=300, blank=True)
    in_dispute = models.BooleanField(default=False, help_text="Stops automatic reminders while a dispute is being sorted out.")
    dispute_note = models.CharField(max_length=300, blank=True)
    reminder_count = models.PositiveSmallIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(total__gte=0) & models.Q(amount_paid__gte=0), name="invoice_amounts_non_negative")]
        indexes = [models.Index(fields=["status", "due_date"]), models.Index(fields=["currency", "status"])]

    def __str__(self):
        return self.number or f"Draft #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = new_token()
        super().save(*args, **kwargs)

    @property
    def is_draft(self):
        return self.status == self.DRAFT

    @property
    def balance(self):
        return max(money.q(self.total - self.amount_paid, self.currency), ZERO)

    @property
    def is_overdue(self):
        return bool(self.status in self.OPEN and self.due_date and self.due_date < timezone.localdate() and self.balance > 0)

    @property
    def display_status(self):
        return "overdue" if self.is_overdue else self.status

    @property
    def display_status_label(self):
        return "Overdue" if self.is_overdue else self.get_status_display()

    @property
    def public_path(self):
        return f"/i/{self.token}/"

    @property
    def days_overdue(self):
        return (timezone.localdate() - self.due_date).days if self.is_overdue else 0

    def company(self):
        """Company details as they were when this invoice was issued; live details only for drafts."""
        return self.company_snapshot or CompanyBilling.load().snapshot()

    def recalc(self, save=True):
        """Recompute subtotal / tax / total from the lines (drafts only)."""
        cur = self.currency
        sub = sum((money.q(i.quantity * i.unit_price, cur) for i in self.items.all()), ZERO)
        disc = min(money.q(self.discount, cur), sub)
        tax = money.q((sub - disc) * (self.tax_percent or 0) / 100, cur)
        self.subtotal, self.discount, self.tax_amount, self.total = money.q(sub, cur), disc, tax, money.q(sub - disc + tax, cur)
        if save:
            self.save(update_fields=["subtotal", "discount", "tax_amount", "total", "updated_at"])
        return self


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=300)
    detail = models.CharField(max_length=500, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit = models.CharField(max_length=20, blank=True, help_text="e.g. hrs, pcs")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def total(self):
        return money.q(self.quantity * self.unit_price, self.invoice.currency)


class InvoiceEvent(models.Model):
    """Append-only audit trail for an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=24)
    detail = models.CharField(max_length=400, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class InvoiceEmail(models.Model):
    """Links an invoice to each email we queued about it. Delivery status is read from the real EmailMessage."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="emails")
    message = models.ForeignKey("mailer.EmailMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=24)
    to = models.CharField(max_length=300, blank=True)
    subject = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


# ------------------------------------------------------------------ payments
class Payment(TimeStamped):
    INITIATED, PENDING, CONFIRMED, REJECTED, FAILED, CANCELLED = "initiated", "pending", "confirmed", "rejected", "failed", "cancelled"
    STATUS = [(INITIATED, "Awaiting payment"), (PENDING, "Pending verification"), (CONFIRMED, "Confirmed"), (REJECTED, "Rejected"), (FAILED, "Failed"), (CANCELLED, "Cancelled")]
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    method = models.ForeignKey(PaymentMethod, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    method_kind = models.CharField(max_length=10, blank=True)
    method_label = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDING, db_index=True)
    source = models.CharField(max_length=10, default="staff", help_text="staff / client / gateway")
    amount = models.DecimalField("Credited to invoice", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3)
    received_currency = models.CharField(max_length=3, blank=True)
    received_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    bank_fee = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reference = models.CharField("Transfer reference", max_length=120, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=400, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    provider_session_id = models.CharField(max_length=200, blank=True)
    provider_txn_id = models.CharField(max_length=200, blank=True)
    refunded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.CharField(max_length=400, blank=True)
    receipt_number = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    receipt_issued_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_txn_id"], condition=~models.Q(provider_txn_id=""), name="uniq_provider_txn"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def __str__(self):
        return f"{self.receipt_number or 'Payment'} {money.fmt(self.amount, self.currency)}"

    @property
    def net_amount(self):
        return max(money.q(self.amount - self.refunded_amount, self.currency), ZERO)

    @property
    def refundable(self):
        return self.net_amount if self.status == self.CONFIRMED else ZERO


class Refund(TimeStamped):
    RECORDED, PENDING, SUCCEEDED, FAILED = "recorded", "pending", "succeeded", "failed"
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, default=RECORDED)
    provider_refund_id = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["payment", "provider_refund_id"], condition=~models.Q(provider_refund_id=""), name="uniq_refund_provider_id")]


class WebhookEvent(models.Model):
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, default="received")  # received processed ignored failed
    error = models.CharField(max_length=300, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="uniq_webhook_event")]


# ------------------------------------------------------------------ company documents (profile PDF) – reuses the Media library
class CompanyDocument(TimeStamped):
    """A version of the company profile. The file itself lives in the existing Media library; this row only records which file
    is the current profile and keeps every older version for the record."""
    PROFILE = "profile"
    kind = models.CharField(max_length=12, default=PROFILE, db_index=True)
    version = models.PositiveIntegerField(default=1)
    asset = models.ForeignKey("core.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    filename = models.CharField(max_length=200, blank=True)
    size = models.PositiveIntegerField(default=0)
    is_current = models.BooleanField(default=True, db_index=True)
    note = models.CharField(max_length=300, blank=True)
    share_token = models.CharField(max_length=40, unique=True, editable=False)
    link_sharing = models.BooleanField("Allow secure link sharing", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-version", "-id"]

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = new_token()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Company profile v{self.version}"

    @property
    def link_path(self):
        return f"/d/{self.share_token}/"


class DocumentShare(models.Model):
    """Records every time a document was attached, linked or deliberately kept internal – picking a file never means it was sent."""
    ATTACH, LINK, INTERNAL = "attach", "link", "internal"
    document = models.ForeignKey(CompanyDocument, on_delete=models.CASCADE, related_name="shares")
    mode = models.CharField(max_length=10, default=INTERNAL, choices=[(ATTACH, "Attached to email"), (LINK, "Secure link in email"), (INTERNAL, "Internal only")])
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    proposal = models.ForeignKey("outbound.Proposal", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    email = models.ForeignKey("mailer.EmailMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
