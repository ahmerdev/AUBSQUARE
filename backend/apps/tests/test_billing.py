"""Billing: money maths, numbering, PDFs, payments & verification, refunds, gateway webhooks, email attachments,
Media-library company profile, permissions, proposal→invoice, historical preservation and every dashboard screen."""
import hashlib
import hmac
import io
import json
import os
import shutil
import tempfile
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from apps.billing import emails, money, services as S
from apps.billing.gateways.stripe import StripeGateway
from apps.billing.models import CompanyBilling, CompanyDocument, DocumentShare, Invoice, NumberSequence, Payment, PaymentMethod, Refund, WebhookEvent
from apps.billing.pdf import invoice_pdf, receipt_pdf
from apps.billing.services import BillingError
from apps.core.media import create_media_asset
from apps.leads.models import Lead
from apps.mailer.models import EmailMessage
from apps.mailer.service import deliver
from apps.outbound.models import Proposal, ProposalItem

from .base import Base

D = Decimal


def company(**kw):
    cb = CompanyBilling.load()
    for k, v in dict(legal_name="Acme Software (Pvt) Ltd", address_line1="Office 4, Clifton", city="Karachi", postal_code="75600", country="Pakistan", email="billing@acme.test",
                     phone="+92 300 1234567", website="https://acme.test", tax_label="NTN", tax_no="1234567-8", invoice_footer="Thank you for your business.", payment_terms_days=14).items():
        setattr(cb, k, v)
    for k, v in kw.items():
        setattr(cb, k, v)
    cb.save()
    return cb


def bank(**kw):
    d = dict(kind="bank_pk", label="Bank transfer (PKR)", is_enabled=True, account_title="Acme Software", bank_name="Test Bank", account_number="0011223344", iban="PK36SCBL0000001123456702")
    d.update(kw)
    return PaymentMethod.objects.create(**d)


def draft(lines=((1, "100.00"),), **kw):
    d = dict(client_name="Ayesha Khan", client_company="Khan Traders", client_email="ayesha@client.test", currency="USD", project_name="Website")
    d.update(kw)
    inv = S.new_draft(None, **d)
    S.replace_items(inv, [{"description": f"Item {i}", "quantity": D(str(q)), "unit_price": D(p), "order": i} for i, (q, p) in enumerate(lines)])
    inv.refresh_from_db()
    return inv


def issued(lines=((1, "100.00"),), **kw):
    return S.issue_invoice(draft(lines, **kw), None)


def pdf_text(data):
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


class BillingBase(Base):
    def setUp(self):
        super().setUp()
        company()
        self.bank = bank()


class MoneyAndTotals(BillingBase):
    def test_half_up_rounding_and_precision_per_currency(self):
        self.assertEqual(money.q("1.005", "USD"), D("1.01"))
        self.assertEqual(money.q("2.5", "JPY"), D("3"))
        self.assertEqual(money.q("1.2345", "KWD"), D("1.235"))
        self.assertEqual(money.minor_units("12.34", "USD"), 1234)
        self.assertEqual(money.minor_units("500", "JPY"), 500)
        self.assertEqual(money.from_minor(1234, "USD"), D("12.34"))
        self.assertEqual(money.fmt("1234.5", "PKR"), "PKR 1,234.50")
        self.assertEqual(money.to_dec("NaN"), D("0"))
        self.assertEqual(money.to_dec("1,200.50"), D("1200.50"))

    def test_totals_discount_and_tax_are_exact_decimals(self):
        inv = draft(((3, "33.33"), (2, "10.10")), discount=D("5.00"), tax_percent=D("16"))
        self.assertEqual(inv.subtotal, D("120.19"))      # 99.99 + 20.20
        self.assertEqual(inv.tax_amount, D("18.43"))      # (120.19-5)*16% = 18.4304
        self.assertEqual(inv.total, D("133.62"))

    def test_discount_never_exceeds_subtotal_and_total_never_negative(self):
        inv = draft(((1, "50.00"),), discount=D("500"))
        self.assertEqual(inv.discount, D("50.00"))
        self.assertEqual(inv.total, D("0.00"))

    def test_zero_total_cannot_be_issued(self):
        with self.assertRaises(BillingError):
            S.issue_invoice(draft(((1, "0"),)), None)

    def test_currency_stays_the_invoice_currency(self):
        inv = issued(currency="PKR")
        self.assertEqual(inv.currency, "PKR")
        self.assertIn("PKR", money.fmt(inv.total, inv.currency))


class NumberingAndDraftRules(BillingBase):
    def test_sequential_unique_numbers_with_configurable_prefix(self):
        company(invoice_prefix="AUB", number_padding=5)
        a, b = issued(), issued()
        y = timezone.localdate().year
        self.assertEqual((a.number, b.number), (f"AUB-{y}-00001", f"AUB-{y}-00002"))

    def test_start_number_can_continue_an_existing_sequence_but_never_reuses(self):
        company(invoice_start_number=250)
        self.assertTrue(issued().number.endswith("-0250"))
        company(invoice_start_number=10)
        self.assertTrue(issued().number.endswith("-0251"))

    def test_database_refuses_duplicate_invoice_numbers(self):
        a = issued()
        b = draft()
        b.number = a.number
        with self.assertRaises(IntegrityError), transaction.atomic():
            b.save()

    def test_number_sequence_take_is_monotonic(self):
        seen = [NumberSequence.take("t") for _ in range(5)]
        self.assertEqual(seen, [1, 2, 3, 4, 5])

    def test_draft_has_no_number_and_is_invisible_to_the_client(self):
        inv = draft()
        self.assertIsNone(inv.number)
        self.assertEqual(self.client.get(inv.public_path).status_code, 404)
        self.assertEqual(self.client.get(f"/i/{inv.token}/pdf/").status_code, 404)

    def test_issuing_requires_company_name_and_a_payment_route(self):
        company(legal_name="", trading_name="")
        with self.assertRaisesMessage(BillingError, "company name"):
            S.issue_invoice(draft(), None)
        company()
        PaymentMethod.objects.all().delete()
        with self.assertRaisesMessage(BillingError, "payment method"):
            S.issue_invoice(draft(), None)

    def test_issued_invoice_cannot_be_edited_through_the_dashboard(self):
        inv = issued()
        self.login(self.root)
        r = self.client.get(reverse("dashboard:invoice_edit", args=[inv.pk]), follow=True)
        self.assertContains(r, "cannot be edited")
        r = self.client.post(reverse("dashboard:invoice_edit", args=[inv.pk]), {"client_name": "Hacker", "item_desc": ["x"], "item_qty": ["1"], "item_price": ["1"]}, follow=True)
        inv.refresh_from_db()
        self.assertEqual(inv.client_name, "Ayesha Khan")

    def test_issuing_twice_is_refused(self):
        inv = issued()
        with self.assertRaises(BillingError):
            S.issue_invoice(inv, None)

    def test_issued_invoice_keeps_a_snapshot_of_company_details(self):
        inv = issued()
        company(legal_name="Totally New Name Ltd", tax_no="9999999-9")
        inv.refresh_from_db()
        txt = pdf_text(invoice_pdf(inv))
        self.assertIn("Acme Software (Pvt) Ltd", txt)
        self.assertNotIn("Totally New Name", txt)
        self.assertEqual(inv.company()["name"], "Acme Software (Pvt) Ltd")
        later = issued()
        self.assertIn("Totally New Name Ltd", pdf_text(invoice_pdf(later)))

    def test_revise_voids_the_old_invoice_and_creates_a_linked_draft(self):
        inv = issued()
        new = S.revise_invoice(inv, None)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.VOID)
        self.assertTrue(new.is_draft)
        self.assertEqual(new.replaces_id, inv.pk)
        self.assertEqual(new.items.count(), 1)
        self.assertTrue(inv.number)  # the old number is kept, never recycled

    def test_cannot_void_after_money_was_received(self):
        inv = issued()
        S.record_payment(inv, None, method=self.bank, amount=D("10"), verify=True, verification_note="statement")
        inv.refresh_from_db()
        with self.assertRaisesMessage(BillingError, "Payments have been received"):
            S.close_invoice(inv, None, Invoice.VOID, "oops")

    def test_closing_needs_a_reason_and_cancels_pending_payments(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("10"))
        with self.assertRaises(BillingError):
            S.close_invoice(inv, None, Invoice.CANCELLED, "")
        S.close_invoice(inv, None, Invoice.CANCELLED, "Issued by mistake")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.CANCELLED)
        with self.assertRaises(BillingError):
            S.record_payment(inv, None, method=self.bank, amount=D("5"))


class PdfContent(BillingBase):
    def test_pdf_contains_company_client_items_tax_and_bank_details(self):
        company(default_tax_percent=D("16"), tax_name="Sales tax")
        inv = issued(((2, "250.00"),), tax_percent=D("16"), tax_name="Sales tax")
        data = invoice_pdf(inv)
        self.assertTrue(data.startswith(b"%PDF"))
        txt = pdf_text(data)
        for needle in ("Acme Software (Pvt) Ltd", "Office 4, Clifton", "NTN: 1234567-8", inv.number, "Khan Traders", "Item 0", "500.00", "Sales tax (16%)", "580.00",
                       "PK36SCBL0000001123456702", "Thank you for your business.", "Page 1 of 1", "HOW TO PAY"):
            self.assertIn(needle, txt, needle)

    def test_long_invoice_paginates_with_page_numbers_and_repeated_header(self):
        inv = issued(tuple((1, "10.00") for _ in range(45)))
        r = PdfReader(io.BytesIO(invoice_pdf(inv)))
        self.assertGreater(len(r.pages), 1)
        last = r.pages[-1].extract_text()
        self.assertIn(f"Page {len(r.pages)} of {len(r.pages)}", last)
        self.assertIn("DESCRIPTION", r.pages[1].extract_text())

    def test_logo_is_embedded_when_it_is_a_local_media_file(self):
        from PIL import Image
        tmp = tempfile.mkdtemp()
        try:
            Image.new("RGB", (400, 120), (236, 0, 140)).save(os.path.join(tmp, "logo.png"))
            with override_settings(MEDIA_ROOT=tmp):
                company(logo_url="/media/logo.png")
                inv = issued()
                images = list(PdfReader(io.BytesIO(invoice_pdf(inv))).pages[0].images)
                self.assertEqual(len(images), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_remote_or_traversal_logo_urls_are_ignored_safely(self):
        company(logo_url="https://evil.test/x.png")
        self.assertTrue(invoice_pdf(issued()).startswith(b"%PDF"))
        company(logo_url="/media/../../etc/passwd")
        self.assertTrue(invoice_pdf(issued()).startswith(b"%PDF"))

    def test_unicode_names_and_xml_special_characters_do_not_break_the_pdf(self):
        inv = issued(client_name="Çağlar <b>&</b> Söhne", project_name="R&D <script>")
        self.assertIn("Söhne", pdf_text(invoice_pdf(inv)))

    def test_void_and_paid_status_are_stamped(self):
        inv = issued()
        S.record_payment(inv, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        inv.refresh_from_db()
        self.assertIn("PAID", pdf_text(invoice_pdf(inv)))

    def test_receipt_pdf_has_receipt_number_amounts_and_verification(self):
        inv = issued(((1, "300.00"),))
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="TRX-77", verify=True, verification_note="seen on statement")
        txt = pdf_text(receipt_pdf(p))
        for needle in ("RCT-", inv.number, "TRX-77", "USD 100.00", "USD 200.00", "Verified"):
            self.assertIn(needle, txt, needle)


class PaymentsAndVerification(BillingBase):
    def test_reported_payment_is_pending_and_does_not_change_the_balance(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="IBFT123")
        inv.refresh_from_db()
        self.assertEqual((p.status, inv.status, inv.amount_paid, inv.balance), (Payment.PENDING, Invoice.ISSUED, D("0"), D("100.00")))
        self.assertIsNone(p.receipt_number)

    def test_confirming_needs_a_verification_note_and_creates_a_receipt(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"))
        with self.assertRaisesMessage(BillingError, "how you verified"):
            S.confirm_payment(p, self.root, "")
        S.confirm_payment(p, self.root, "Seen on HBL statement")
        p.refresh_from_db(); inv.refresh_from_db()
        self.assertEqual((p.status, inv.status), (Payment.CONFIRMED, Invoice.PAID))
        self.assertRegex(p.receipt_number, r"^RCT-\d{4}-\d{4}$")
        self.assertEqual(p.verified_by, self.root)
        self.assertIsNotNone(inv.paid_at)

    def test_confirming_twice_is_idempotent(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"))
        S.confirm_payment(p, self.root, "ok")
        first = Payment.objects.get(pk=p.pk).receipt_number
        S.confirm_payment(p, self.root, "ok again")
        self.assertEqual(Payment.objects.get(pk=p.pk).receipt_number, first)
        self.assertEqual(Payment.objects.filter(status=Payment.CONFIRMED).count(), 1)

    def test_partial_payments_move_the_invoice_through_partially_paid_to_paid(self):
        inv = issued(((1, "1000.00"),))
        S.record_payment(inv, None, method=self.bank, amount=D("400"), verify=True, verification_note="a")
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.amount_paid, inv.balance), (Invoice.PARTIAL, D("400.00"), D("600.00")))
        S.record_payment(inv, None, method=self.bank, amount=D("600"), verify=True, verification_note="b")
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.balance), (Invoice.PAID, D("0.00")))
        self.assertEqual(inv.payments.filter(status="confirmed").count(), 2)

    def test_overpayment_is_refused_for_manual_payments(self):
        inv = issued(((1, "100.00"),))
        with self.assertRaisesMessage(BillingError, "more than the remaining balance"):
            S.record_payment(inv, None, method=self.bank, amount=D("100.01"))

    def test_two_pending_payments_cannot_both_be_confirmed_past_the_balance(self):
        inv = issued(((1, "100.00"),))
        a = S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="A")
        b = S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="B")
        S.confirm_payment(a, self.root, "ok")
        with self.assertRaises(BillingError):
            S.confirm_payment(b, self.root, "ok")

    def test_rejected_payment_never_counts(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"))
        with self.assertRaises(BillingError):
            S.reject_payment(p, self.root, "")
        S.reject_payment(p, self.root, "Not on the statement")
        inv.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((p.status, inv.amount_paid), (Payment.REJECTED, D("0")))
        with self.assertRaises(BillingError):
            S.confirm_payment(p, self.root, "now it is")

    def test_duplicate_reference_and_amount_is_blocked(self):
        inv = issued(((1, "500.00"),))
        S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="DUP1")
        with self.assertRaisesMessage(BillingError, "already recorded"):
            S.record_payment(inv, None, method=self.bank, amount=D("100"), reference="dup1")

    def test_foreign_currency_receipt_needs_the_real_exchange_rate_and_is_recorded(self):
        inv = issued(((1, "200.00"),), currency="USD")
        with self.assertRaisesMessage(BillingError, "exchange rate"):
            S.record_payment(inv, None, method=self.bank, amount=D("200"), received_currency="PKR", received_amount=D("56000"))
        p = S.record_payment(inv, None, method=self.bank, amount=D("198.50"), received_currency="PKR", received_amount=D("55580"), exchange_rate=D("280.00"), bank_fee=D("1.50"))
        self.assertEqual((p.received_currency, p.received_amount, p.exchange_rate, p.bank_fee, p.currency, p.amount), ("PKR", D("55580.00"), D("280"), D("1.50"), "USD", D("198.50")))

    def test_outstanding_is_never_mixed_across_currencies(self):
        issued(((1, "100.00"),), currency="USD")
        issued(((1, "5000.00"),), currency="PKR")
        company(enabled_currencies="USD,PKR")
        self.login(self.root)
        r = self.client.get(reverse("dashboard:invoices"))
        got = {c: (o, v) for c, o, v in r.context["outstanding"]}
        self.assertEqual(got["USD"][0], D("100.00"))
        self.assertEqual(got["PKR"][0], D("5000.00"))

    def test_client_can_report_a_payment_but_it_stays_pending(self):
        inv = issued()
        r = self.client.post(inv.public_path, {"action": "report_payment", "reference": "MYREF9", "amount": "100"})
        self.assertContains(r, "noted your payment")
        p = inv.payments.get()
        inv.refresh_from_db()
        self.assertEqual((p.status, p.source, inv.status), (Payment.PENDING, "client", Invoice.ISSUED))

    def test_client_report_needs_a_reference(self):
        inv = issued()
        r = self.client.post(inv.public_path, {"action": "report_payment", "reference": "", "amount": "100"})
        self.assertContains(r, "transfer reference")
        self.assertEqual(inv.payments.count(), 0)


class Refunds(BillingBase):
    def test_manual_refund_reduces_paid_and_reopens_the_balance(self):
        inv = issued(((1, "100.00"),))
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        S.refund_payment(p, self.root, D("30"), "Client cancelled part")
        inv.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((inv.amount_paid, inv.balance, inv.status, p.refunded_amount), (D("70.00"), D("30.00"), Invoice.PARTIAL, D("30.00")))
        self.assertEqual(Refund.objects.get().created_by, self.root)

    def test_refund_cannot_exceed_the_payment_and_needs_a_reason(self):
        inv = issued(((1, "100.00"),))
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        with self.assertRaises(BillingError):
            S.refund_payment(p, self.root, D("100.01"), "too much")
        with self.assertRaises(BillingError):
            S.refund_payment(p, self.root, D("10"), "")
        S.refund_payment(p, self.root, D("100"), "full refund")
        with self.assertRaises(BillingError):
            S.refund_payment(p, self.root, D("1"), "again")

    def test_pending_payment_cannot_be_refunded(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("50"))
        with self.assertRaises(BillingError):
            S.refund_payment(p, self.root, D("10"), "x")


SECRET, WHSEC = "sk_test_x", "whsec_test"


def stripe_method(**kw):
    d = dict(kind="stripe", label="Card (Stripe)", is_enabled=True, mode="test", verified_eligible=True)
    d.update(kw)
    return PaymentMethod.objects.create(**d)


def sign(body: bytes, secret=WHSEC, ts=None):
    ts = int(ts or time.time())
    return f"t={ts},v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


@mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY_TEST": SECRET, "STRIPE_WEBHOOK_SECRET_TEST": WHSEC})
class StripeGatewayAndWebhooks(BillingBase):
    def setUp(self):
        super().setUp()
        self.card = stripe_method()
        self.inv = issued(((1, "250.00"),), currency="USD")
        self.pay = Payment.objects.create(invoice=self.inv, status=Payment.INITIATED, source="gateway", provider="stripe", amount=D("250.00"), currency="USD", method=self.card, method_kind="stripe",
                                          method_label="Card", provider_session_id="cs_1")

    def event(self, kind="checkout.session.completed", eid="evt_1", amount=25000, cur="usd", status="paid", **obj):
        o = {"id": "cs_1", "payment_intent": "pi_1", "amount_total": amount, "currency": cur, "payment_status": status, "metadata": {"payment_id": str(self.pay.pk)}, "client_reference_id": str(self.pay.pk)}
        o.update(obj)
        return json.dumps({"id": eid, "type": kind, "data": {"object": o}}).encode()

    def post(self, body, sig=None):
        return self.client.post("/billing/webhooks/stripe/", body, content_type="application/json", HTTP_STRIPE_SIGNATURE=sig if sig is not None else sign(body))

    def test_valid_signed_payment_confirms_the_payment_and_issues_a_receipt(self):
        r = self.post(self.event())
        self.assertEqual((r.status_code, r.content), (200, b"processed"))
        self.pay.refresh_from_db(); self.inv.refresh_from_db()
        self.assertEqual((self.pay.status, self.pay.provider_txn_id, self.inv.status), (Payment.CONFIRMED, "pi_1", Invoice.PAID))
        self.assertTrue(self.pay.receipt_number)

    def test_bad_missing_wrong_secret_and_stale_signatures_are_rejected(self):
        body = self.event()
        for sig in ("", "garbage", sign(body, secret="whsec_other"), sign(body, ts=time.time() - 3600), f"t={int(time.time())},v1=" + "0" * 64):
            self.assertEqual(self.post(body, sig=sig).status_code, 400, sig)
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, Payment.INITIATED)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_tampered_body_fails_the_signature(self):
        body = self.event()
        sig = sign(body)
        self.assertEqual(self.post(body.replace(b"25000", b"1"), sig=sig).status_code, 400)

    def test_duplicate_delivery_is_idempotent(self):
        body = self.event()
        self.assertEqual(self.post(body).content, b"processed")
        self.assertEqual(self.post(body).content, b"duplicate")
        self.assertEqual(Payment.objects.filter(status="confirmed").count(), 1)
        self.assertEqual(WebhookEvent.objects.filter(event_id="evt_1").count(), 1)
        self.assertEqual(Invoice.objects.get(pk=self.inv.pk).amount_paid, D("250.00"))

    def test_same_transaction_under_a_different_event_id_is_not_recorded_twice(self):
        self.post(self.event(eid="evt_1"))
        other = Payment.objects.create(invoice=self.inv, status=Payment.INITIATED, source="gateway", provider="stripe", amount=D("1.00"), currency="USD", provider_session_id="cs_2")
        body = self.event(eid="evt_2", id="cs_2", metadata={"payment_id": str(other.pk)}, client_reference_id=str(other.pk))
        self.post(body)
        other.refresh_from_db()
        self.assertNotEqual(other.status, Payment.CONFIRMED)
        self.assertEqual(Invoice.objects.get(pk=self.inv.pk).amount_paid, D("250.00"))

    def test_amount_mismatch_is_sent_to_a_human_not_auto_confirmed(self):
        self.post(self.event(amount=100))
        self.pay.refresh_from_db(); self.inv.refresh_from_db()
        self.assertEqual((self.pay.status, self.inv.amount_paid), (Payment.PENDING, D("0")))
        self.assertIn("differs", self.pay.failure_reason)

    def test_currency_mismatch_is_not_auto_confirmed(self):
        self.post(self.event(cur="eur"))
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, Payment.PENDING)

    def test_unpaid_async_session_is_ignored_until_it_succeeds(self):
        self.assertEqual(self.post(self.event(status="unpaid")).content, b"ignored")
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, Payment.INITIATED)

    def test_failed_payment_is_recorded_and_the_client_is_emailed(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post(json.dumps({"id": "evt_f", "type": "checkout.session.async_payment_failed", "data": {"object": {"id": "cs_1", "metadata": {"payment_id": str(self.pay.pk)}}}}).encode())
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, Payment.FAILED)
        self.assertTrue(EmailMessage.objects.filter(subject__icontains="did not go through").exists())

    def test_expired_checkout_is_cancelled(self):
        self.post(json.dumps({"id": "evt_e", "type": "checkout.session.expired", "data": {"object": {"id": "cs_1", "metadata": {"payment_id": str(self.pay.pk)}}}}).encode())
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, Payment.CANCELLED)

    def test_provider_side_refund_is_recorded_once(self):
        self.post(self.event())
        body = json.dumps({"id": "evt_r", "type": "charge.refunded", "data": {"object": {"payment_intent": "pi_1", "currency": "usd", "refunds": {"data": [{"id": "re_1", "amount": 5000}]}}}}).encode()
        self.assertEqual(self.post(body).content, b"processed")
        body2 = body.replace(b"evt_r", b"evt_r2")
        self.post(body2)
        self.pay.refresh_from_db(); self.inv.refresh_from_db()
        self.assertEqual((self.pay.refunded_amount, self.inv.amount_paid, Refund.objects.count()), (D("50.00"), D("200.00"), 1))

    def test_webhook_is_404_when_the_gateway_is_disabled_and_get_is_not_allowed(self):
        self.card.is_enabled = False
        self.card.save()
        self.assertEqual(self.post(self.event()).status_code, 404)
        self.card.is_enabled = True
        self.card.save()
        self.assertEqual(self.client.get("/billing/webhooks/stripe/").status_code, 405)
        self.assertEqual(self.client.post("/billing/webhooks/paypal/", b"{}", content_type="application/json").status_code, 404)

    def test_checkout_creation_calls_stripe_with_server_side_amount_and_returns_the_hosted_url(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"id": "cs_new", "url": "https://checkout.stripe.test/c/pay"}
        with mock.patch("apps.billing.gateways.stripe.requests.post", return_value=resp) as post:
            url = S.start_checkout(self.inv, self.card, "https://x.test/ok", "https://x.test/cancel")
        self.assertEqual(url, "https://checkout.stripe.test/c/pay")
        data = post.call_args.kwargs["data"]
        self.assertEqual(data["line_items[0][price_data][unit_amount]"], "25000")
        self.assertEqual(data["line_items[0][price_data][currency]"], "usd")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], f"Bearer {SECRET}")
        self.assertEqual(Payment.objects.filter(status=Payment.INITIATED, provider_session_id="cs_new").count(), 1)

    def test_a_redirect_back_from_the_provider_never_marks_anything_paid(self):
        r = self.client.get(self.inv.public_path + "?paid=return")
        self.assertContains(r, "confirmed automatically")
        self.inv.refresh_from_db(); self.pay.refresh_from_db()
        self.assertEqual((self.inv.status, self.pay.status), (Invoice.ISSUED, Payment.INITIATED))

    def test_provider_error_marks_the_attempt_failed_with_a_safe_message(self):
        resp = mock.Mock(status_code=400)
        resp.json.return_value = {"error": {"message": "Invalid currency"}}
        with mock.patch("apps.billing.gateways.stripe.requests.post", return_value=resp):
            with self.assertRaisesMessage(BillingError, "Invalid currency"):
                S.start_checkout(self.inv, self.card, "https://x.test/ok", "https://x.test/cancel")
        self.assertTrue(Payment.objects.filter(status=Payment.FAILED).exists())

    def test_gateway_refund_goes_through_the_provider_api(self):
        self.post(self.event())
        self.pay.refresh_from_db()
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"id": "re_9", "status": "succeeded"}
        with mock.patch("apps.billing.gateways.stripe.requests.post", return_value=resp) as post:
            S.refund_payment(self.pay, self.root, D("100"), "Client request")
        self.assertEqual(post.call_args.kwargs["data"]["payment_intent"], "pi_1")
        self.assertEqual(post.call_args.kwargs["data"]["amount"], "10000")
        self.assertEqual(Refund.objects.get().provider_refund_id, "re_9")
        self.assertEqual(Invoice.objects.get(pk=self.inv.pk).amount_paid, D("150.00"))


class GatewayStaysOffUntilConfigured(BillingBase):
    def test_gateway_is_not_ready_without_eligibility_confirmation_or_secrets(self):
        m = stripe_method(verified_eligible=False)
        self.assertFalse(StripeGateway(m).configured())
        m.verified_eligible = True
        m.save()
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("STRIPE_SECRET_KEY_TEST", "STRIPE_WEBHOOK_SECRET_TEST"):
                os.environ.pop(k, None)
            self.assertFalse(StripeGateway(m).configured())
            self.assertEqual(sorted(StripeGateway(m).missing()), ["STRIPE_SECRET_KEY_TEST", "STRIPE_WEBHOOK_SECRET_TEST"])
            inv = issued()
            self.assertEqual([x["kind"] for x in inv.methods_snapshot], ["bank_pk"])  # card is not offered
            with self.assertRaises(BillingError):
                S.start_checkout(inv, m, "https://x/ok", "https://x/no")

    def test_public_page_shows_no_card_button_when_the_gateway_is_not_ready(self):
        stripe_method(verified_eligible=False)
        inv = issued()
        r = self.client.get(inv.public_path)
        self.assertNotContains(r, "Pay ")
        self.assertContains(r, "PK36SCBL0000001123456702")

    def test_form_refuses_to_enable_a_gateway_without_the_eligibility_tick(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:billing_method_new") + "?kind=stripe", {"kind": "stripe", "label": "Card", "is_enabled": "on", "mode": "test", "reference_format": "{invoice}"})
        self.assertContains(r, "stay off until you confirm")
        self.assertFalse(PaymentMethod.objects.filter(kind="stripe").exists())

    def test_wire_and_bank_forms_validate_required_details(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:billing_method_new") + "?kind=wire", {"kind": "wire", "label": "Wire", "is_enabled": "on", "account_title": "Acme", "account_number": "123", "reference_format": "{invoice}"})
        self.assertContains(r, "SWIFT/BIC")
        r = self.client.post(reverse("dashboard:billing_method_new") + "?kind=bank_pk", {"kind": "bank_pk", "label": "Bank", "iban": "NOT-AN-IBAN", "reference_format": "{invoice}"})
        self.assertContains(r, "does not look like an IBAN")


class EmailsAndAttachments(BillingBase):
    def send(self, inv, kind="issued", **kw):
        with self.captureOnCommitCallbacks(execute=True):
            return emails.send_invoice_email(inv, self.root, kind, **kw)

    def test_issued_email_attaches_the_real_pdf_and_logs_it_on_the_invoice(self):
        inv = issued()
        msg = self.send(inv)
        msg.refresh_from_db()
        self.assertEqual(msg.status, EmailMessage.SENT)
        self.assertEqual(msg.attachments_info[0]["name"], f"Invoice-{inv.number}.pdf")
        sent = mail.outbox[-1]
        self.assertEqual(len(sent.attachments), 1)
        name, data, mime = sent.attachments[0]
        self.assertEqual((name, mime), (f"Invoice-{inv.number}.pdf", "application/pdf"))
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertIn(inv.number, sent.subject)
        self.assertIn(f"/i/{inv.token}/", sent.body)
        self.assertIn("PK36SCBL0000001123456702", sent.body)
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.emails.count()), (Invoice.SENT, 1))

    def test_email_without_pdf_when_unticked(self):
        msg = self.send(issued(), attach_pdf=False)
        self.assertEqual(msg.attachment_refs, [])

    def test_draft_cannot_be_emailed_and_missing_address_is_explained(self):
        with self.assertRaisesMessage(BillingError, "Issue the invoice"):
            emails.send_invoice_email(draft(), self.root, "issued")
        with self.assertRaisesMessage(BillingError, "email address"):
            emails.send_invoice_email(issued(client_email=""), self.root, "issued")

    def test_reminders_are_blocked_for_paid_closed_and_disputed_invoices(self):
        paid = issued()
        S.record_payment(paid, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        paid.refresh_from_db()
        with self.assertRaisesMessage(BillingError, "already paid"):
            emails.send_invoice_email(paid, self.root, "reminder")
        disputed = issued()
        disputed.in_dispute = True
        disputed.save()
        with self.assertRaisesMessage(BillingError, "disputed"):
            emails.send_invoice_email(disputed, self.root, "overdue")

    def test_receipt_email_attaches_the_receipt_pdf(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        self.send(inv, "payment_received", payment=p)
        att = mail.outbox[-1].attachments[0]
        self.assertEqual(att[0], f"Receipt-{p.receipt_number}.pdf")
        self.assertTrue(att[1].startswith(b"%PDF"))

    def test_failed_send_is_recorded_honestly_and_can_retry(self):
        inv = issued()
        with mock.patch("apps.mailer.service.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
            msg = self.send(inv)
        msg.refresh_from_db()
        self.assertEqual(msg.status, EmailMessage.FAILED)
        self.assertEqual(emails.delivery_label(msg), "Failed – will retry")
        self.assertTrue(deliver(msg.pk))
        msg.refresh_from_db()
        self.assertEqual((msg.status, emails.delivery_label(msg)), (EmailMessage.SENT, "Accepted by mail server"))

    def test_missing_attachment_is_reported_before_anything_is_queued(self):
        from apps.mailer.service import queue_email
        with self.assertRaises(Exception):
            queue_email(["a@b.test"], "x", "y", attachments=[{"kind": "media", "id": 999999}])
        self.assertEqual(EmailMessage.objects.count(), 0)

    def test_all_email_templates_build(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"), verify=True, verification_note="ok")
        inv.refresh_from_db()
        for k in emails.KINDS:
            subj, body = emails.build(k, inv, p, D("10"))
            self.assertTrue(subj and body, k)
            self.assertNotIn("{", subj)

    def test_scheduled_reminders_respect_settings_limits_and_paid_state(self):
        company(send_reminders=True, remind_before_days=3, remind_every_days=7, max_reminders=2)
        inv = issued(due_date=timezone.localdate() - timedelta(days=5))
        inv.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            res = S.billing_checks()
        self.assertEqual((res["reminders"], res["overdue_alerts"]), (1, 1))
        inv.refresh_from_db()
        self.assertEqual(inv.reminder_count, 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(S.billing_checks()["reminders"], 0)  # too soon
        company(send_reminders=False)
        Invoice.objects.filter(pk=inv.pk).update(last_reminder_at=timezone.now() - timedelta(days=30))
        self.assertEqual(S.billing_checks()["reminders"], 0)  # switched off by default


def pdf_upload(name="profile.pdf", data=b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"):
    return SimpleUploadedFile(name, data, content_type="application/pdf")


class CompanyProfileFromMediaLibrary(BillingBase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.ov = override_settings(MEDIA_ROOT=self.tmp)
        self.ov.enable()
        self.addCleanup(lambda: (self.ov.disable(), shutil.rmtree(self.tmp, ignore_errors=True)))

    def test_pdf_uploaded_once_to_the_existing_library_can_be_selected(self):
        a = create_media_asset(pdf_upload(), self.root)
        self.assertEqual((a.kind, a.mime_type), ("document", "application/pdf"))
        doc = S.set_company_profile(a, self.root, "2026 edition")
        self.assertEqual((doc.version, doc.is_current, doc.filename, doc.asset_id), (1, True, a.download_name, a.pk))

    def test_selecting_the_profile_does_not_email_or_share_it(self):
        S.set_company_profile(create_media_asset(pdf_upload(), self.root), self.root)
        self.assertEqual((EmailMessage.objects.count(), DocumentShare.objects.count()), (0, 0))

    def test_non_pdf_and_fake_pdf_are_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            create_media_asset(SimpleUploadedFile("evil.pdf", b"MZ not a pdf"), self.root)
        img = create_media_asset(SimpleUploadedFile("a.txt", b"hello"), self.root)
        with self.assertRaises(BillingError):
            S.set_company_profile(img, self.root)
        with self.assertRaises(BillingError):
            S.set_company_profile(None, self.root)

    def test_replacing_creates_a_new_version_and_keeps_the_old_one(self):
        a = create_media_asset(pdf_upload("v1.pdf"), self.root)
        b = create_media_asset(pdf_upload("v2.pdf"), self.root)
        S.set_company_profile(a, self.root)
        S.set_company_profile(b, self.root)
        docs = list(CompanyDocument.objects.order_by("version"))
        self.assertEqual([(d.version, d.is_current) for d in docs], [(1, False), (2, True)])
        self.assertEqual(S.current_profile().asset_id, b.pk)

    def test_email_can_attach_link_or_skip_the_profile(self):
        a = create_media_asset(pdf_upload("Acme-Profile.pdf"), self.root)
        doc = S.set_company_profile(a, self.root)
        inv = issued()
        with self.captureOnCommitCallbacks(execute=True):
            m1 = emails.send_invoice_email(inv, self.root, "issued", profile_mode="attach")
        names = [x[0] for x in mail.outbox[-1].attachments]
        self.assertEqual(sorted(names), sorted([f"Invoice-{inv.number}.pdf", a.download_name]))
        with self.captureOnCommitCallbacks(execute=True):
            m2 = emails.send_invoice_email(inv, self.root, "reminder", profile_mode="link")
        self.assertEqual(len(mail.outbox[-1].attachments), 1)
        self.assertIn(f"/d/{doc.share_token}/", mail.outbox[-1].body)
        self.assertIn("secure link", mail.outbox[-1].body)
        with self.captureOnCommitCallbacks(execute=True):
            emails.send_invoice_email(inv, self.root, "reminder", profile_mode="none")
        self.assertNotIn("/d/", mail.outbox[-1].body)
        self.assertEqual(sorted(DocumentShare.objects.values_list("mode", flat=True)), ["attach", "link"])

    def test_profile_mode_without_a_selected_profile_is_an_error(self):
        with self.assertRaisesMessage(BillingError, "No company profile"):
            emails.send_invoice_email(issued(), self.root, "issued", profile_mode="attach")

    def test_shared_link_serves_the_pdf_and_can_be_switched_off(self):
        doc = S.set_company_profile(create_media_asset(pdf_upload(), self.root), self.root)
        r = self.client.get(doc.link_path)
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow, noarchive")
        doc.link_sharing = False
        doc.save()
        self.assertEqual(self.client.get(doc.link_path).status_code, 404)
        self.assertEqual(self.client.get("/d/not-a-token/").status_code, 404)

    def test_profile_versions_cannot_be_deleted_from_the_media_library(self):
        a = create_media_asset(pdf_upload(), self.root)
        S.set_company_profile(a, self.root)
        self.login(self.root)
        r = self.client.post(reverse("dashboard:media_delete", args=[a.pk]), follow=True)
        self.assertContains(r, "saved version of your company profile")
        self.assertTrue(a.__class__.objects.filter(pk=a.pk).exists())

    def test_dashboard_selects_the_file_picked_in_the_media_picker(self):
        a = create_media_asset(pdf_upload(), self.root)
        self.login(self.root)
        r = self.client.post(reverse("dashboard:company_profile"), {"action": "select", "file_url": a.url, "note": "first"}, follow=True)
        self.assertContains(r, "NOT emailed")
        self.assertEqual(S.current_profile().asset_id, a.pk)
        r = self.client.post(reverse("dashboard:company_profile"), {"action": "select", "file_url": "/media/uploads/nope.pdf"}, follow=True)
        self.assertContains(r, "Choose a PDF")

    def test_proposal_send_can_attach_the_profile(self):
        a = create_media_asset(pdf_upload("Prof.pdf"), self.root)
        S.set_company_profile(a, self.root)
        pr = Proposal.objects.create(title="Site", client_name="Sara", client_email="sara@client.test")
        ProposalItem.objects.create(proposal=pr, description="Build", quantity=1, unit_price=100)
        self.login(self.root)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("dashboard:proposal_action", args=[pr.pk]), {"action": "send", "profile_mode": "attach"})
        self.assertEqual([x[0] for x in mail.outbox[-1].attachments], [a.download_name])
        self.assertEqual(DocumentShare.objects.get().proposal_id, pr.pk)


class ProposalToInvoice(BillingBase):
    def won(self, tax="0", discount="0"):
        pr = Proposal.objects.create(title="Website redesign", client_name="Sara Ali", client_company="Ali & Co", client_email="sara@client.test", currency="USD", tax_percent=D(tax), discount=D(discount),
                                     status=Proposal.WON, terms="50% upfront")
        ProposalItem.objects.create(proposal=pr, description="Design", quantity=1, unit_price=D("1000"), order=0)
        ProposalItem.objects.create(proposal=pr, description="Build", quantity=2, unit_price=D("500"), order=1)
        return pr

    def test_full_conversion_copies_client_lines_currency_and_creates_only_a_draft(self):
        pr = self.won(tax="10")
        before = EmailMessage.objects.count()
        inv = S.invoice_from_proposal(pr, self.root, "full")
        self.assertEqual((inv.status, inv.number, inv.currency, inv.client_name, inv.client_company, inv.proposal_id), ("draft", None, "USD", "Sara Ali", "Ali & Co", pr.pk))
        self.assertEqual(inv.items.count(), 2)
        self.assertEqual(inv.total, pr.total)
        self.assertEqual(EmailMessage.objects.count(), before)
        self.assertEqual(Proposal.objects.get(pk=pr.pk).status, Proposal.WON)

    def test_only_won_proposals_can_be_invoiced(self):
        pr = self.won()
        pr.status = Proposal.SENT
        pr.save()
        with self.assertRaisesMessage(BillingError, "marked Won"):
            S.invoice_from_proposal(pr, self.root)

    def test_duplicate_full_invoice_is_blocked(self):
        pr = self.won()
        S.invoice_from_proposal(pr, self.root, "full")
        with self.assertRaisesMessage(BillingError, "already"):
            S.invoice_from_proposal(pr, self.root, "full")

    def test_deposit_then_final_adds_up_to_the_proposal_total(self):
        pr = self.won(tax="16")
        dep = S.invoice_from_proposal(pr, self.root, "deposit", percent="50")
        self.assertEqual(dep.total, money.q(pr.total / 2, "USD"))
        with self.assertRaises(BillingError):
            S.invoice_from_proposal(pr, self.root, "deposit", percent="50")  # duplicate deposit
        fin = S.invoice_from_proposal(pr, self.root, "final")
        self.assertAlmostEqual(float(dep.total + fin.total), float(pr.total), delta=0.01)
        with self.assertRaisesMessage(BillingError, "invoiced in full"):
            S.invoice_from_proposal(pr, self.root, "milestone", amount="10")

    def test_milestones_cannot_exceed_what_is_left(self):
        pr = self.won()
        S.invoice_from_proposal(pr, self.root, "milestone", amount="1500", label="M1")
        S.invoice_from_proposal(pr, self.root, "milestone", amount="400", label="M2")
        with self.assertRaisesMessage(BillingError, "more than what is left"):
            S.invoice_from_proposal(pr, self.root, "milestone", amount="200", label="M3")

    def test_voided_invoice_frees_the_amount_again(self):
        pr = self.won()
        inv = S.invoice_from_proposal(pr, self.root, "full")
        S.issue_invoice(inv, None)
        S.close_invoice(Invoice.objects.get(pk=inv.pk), None, Invoice.VOID, "wrong client")
        self.assertEqual(S.proposal_billing(pr)["remaining"], pr.total)
        S.invoice_from_proposal(pr, self.root, "full")

    def test_dashboard_flow_creates_a_draft_and_redirects_to_the_editor(self):
        pr = self.won()
        self.login(self.root)
        r = self.client.post(reverse("dashboard:proposal_invoice", args=[pr.pk]), {"mode": "deposit", "percent": "30", "label": "30% deposit"})
        inv = Invoice.objects.get(proposal=pr)
        self.assertRedirects(r, reverse("dashboard:invoice_edit", args=[inv.pk]))
        r = self.client.get(reverse("dashboard:proposal_detail", args=[pr.pk]))
        self.assertContains(r, "Create draft invoice")

    def test_manual_invoice_without_a_proposal_is_allowed(self):
        inv = issued(client_name="Walk-in Client")
        self.assertIsNone(inv.proposal_id)
        self.assertTrue(inv.number)


class PermissionsAndPrivacy(BillingBase):
    def setUp(self):
        super().setUp()
        self.sales = self.make_user("sales@example.com", "sales_manager")
        self.reader = self.make_user("reader@example.com", "read_only")
        self.analyst = self.make_user("analyst@example.com", "analyst")
        self.inv = issued()
        self.pending = S.record_payment(self.inv, None, method=self.bank, amount=D("50"))

    def test_anonymous_users_are_sent_to_login_for_every_billing_screen(self):
        for name, args in [("invoices", []), ("invoice_new", []), ("invoice_detail", [self.inv.pk]), ("payments", []), ("billing_reports", []), ("billing_settings", []), ("billing_methods", []), ("company_profile", [])]:
            r = self.client.get(reverse(f"dashboard:{name}", args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("login", r["Location"])

    def test_sales_manager_can_draft_and_send_but_not_issue_verify_void_or_see_bank_settings(self):
        self.login(self.sales)
        self.assertEqual(self.client.get(reverse("dashboard:invoices")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:invoice_new")).status_code, 200)
        d = draft()
        r = self.client.post(reverse("dashboard:invoice_action", args=[d.pk]), {"action": "issue", "confirm": "yes"}, follow=True)
        self.assertContains(r, "permission")
        self.assertTrue(Invoice.objects.get(pk=d.pk).is_draft)
        r = self.client.post(reverse("dashboard:invoice_action", args=[self.inv.pk]), {"action": "void", "reason": "because"}, follow=True)
        self.assertEqual(Invoice.objects.get(pk=self.inv.pk).status, Invoice.ISSUED)
        self.assertEqual(self.client.get(reverse("dashboard:payments")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:billing_methods")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:billing_settings")).status_code, 403)
        self.assertEqual(self.client.post(reverse("dashboard:payment_action", args=[self.pending.pk]), {"action": "confirm", "checked": "1", "note": "x"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:billing_reports")).status_code, 403)

    def test_payment_verification_and_refund_need_their_own_permissions(self):
        pay_only = self.make_user("rec@example.com", "support_agent")
        from apps.accounts.models import Role
        role = Role.objects.create(name="Biller", slug="biller", permissions={"dashboard": ["view"], "invoices": ["view"], "payments": ["view", "create"]})
        pay_only.role = role
        pay_only.save()
        self.login(pay_only)
        r = self.client.post(reverse("dashboard:invoice_payment", args=[self.inv.pk]), {"amount": "20", "reference": "R1", "verify": "1", "verification_note": "x"}, follow=True)
        self.assertContains(r, "verification permission")
        r = self.client.post(reverse("dashboard:invoice_payment", args=[self.inv.pk]), {"amount": "20", "reference": "R2"}, follow=True)
        self.assertEqual(Payment.objects.filter(reference="R2", status="pending").count(), 1)
        r = self.client.post(reverse("dashboard:payment_action", args=[self.pending.pk]), {"action": "confirm", "checked": "1", "note": "x"}, follow=True)
        self.assertContains(r, "permission to verify")
        self.assertEqual(Payment.objects.get(pk=self.pending.pk).status, Payment.PENDING)

    def test_refunds_need_payments_edit(self):
        S.confirm_payment(self.pending, self.root, "ok")
        verifier = self.make_user("ver@example.com", "support_agent")
        from apps.accounts.models import Role
        verifier.role = Role.objects.create(name="Verifier", slug="verifier", permissions={"dashboard": ["view"], "payments": ["view", "approve"]})
        verifier.save()
        self.login(verifier)
        r = self.client.post(reverse("dashboard:payment_action", args=[self.pending.pk]), {"action": "refund", "amount": "10", "note": "x"}, follow=True)
        self.assertContains(r, "permission to refund")
        self.assertFalse(Refund.objects.exists())

    def test_read_only_staff_see_invoices_but_not_bank_details_or_settings(self):
        self.login(self.reader)
        self.assertEqual(self.client.get(reverse("dashboard:invoices")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:billing_settings")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:billing_methods")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:payments")).status_code, 403)
        r = self.client.post(reverse("dashboard:invoice_action", args=[self.inv.pk]), {"action": "note", "body": "x"})
        self.assertEqual(self.inv.events.filter(kind="note").count(), 0)

    def test_settings_cannot_be_changed_without_edit_permission(self):
        from apps.accounts.models import Role
        v = self.make_user("v@example.com", "support_agent")
        v.role = Role.objects.create(name="SetView", slug="setview", permissions={"dashboard": ["view"], "billing_settings": ["view"]})
        v.save()
        self.login(v)
        self.assertEqual(self.client.get(reverse("dashboard:billing_settings")).status_code, 200)
        r = self.client.post(reverse("dashboard:billing_settings"), {"legal_name": "Hijacked"}, follow=True)
        self.assertContains(r, "permission")
        self.assertEqual(CompanyBilling.load().legal_name, "Acme Software (Pvt) Ltd")

    def test_public_links_are_unguessable_and_scoped_to_their_own_invoice(self):
        other = issued()
        self.assertEqual(self.client.get("/i/short/").status_code, 404)
        self.assertEqual(self.client.get(self.inv.public_path).status_code, 200)
        S.confirm_payment(self.pending, self.root, "ok")
        mine = self.pending
        self.assertEqual(self.client.get(f"/i/{self.inv.token}/receipt/{mine.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/i/{other.token}/receipt/{mine.pk}/").status_code, 404)  # IDOR: another invoice's token
        self.assertGreaterEqual(len(self.inv.token), 28)

    def test_public_pages_are_private_and_not_cached(self):
        r = self.client.get(self.inv.public_path)
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertContains(r, 'name="robots"')

    def test_pdf_downloads_require_login_in_the_dashboard(self):
        self.assertEqual(self.client.get(reverse("dashboard:invoice_pdf", args=[self.inv.pk])).status_code, 302)
        self.login(self.root)
        r = self.client.get(reverse("dashboard:invoice_pdf", args=[self.inv.pk]))
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))

    def test_csv_export_is_formula_safe_and_permission_gated(self):
        d = draft(client_name="=HYPERLINK(\"http://evil\")")
        S.issue_invoice(d, None)
        self.login(self.reader)
        self.assertEqual(self.client.get(reverse("dashboard:invoices_export")).status_code, 403)
        self.login(self.root)
        body = self.client.get(reverse("dashboard:invoices_export")).content.decode()
        self.assertIn("'=HYPERLINK", body)

    def test_new_permission_modules_exist_and_defaults_are_granted(self):
        from apps.accounts.models import Role
        sa = Role.objects.get(slug="super_admin")
        for m in ("invoices", "payments", "billing_reports", "billing_settings"):
            self.assertIn(m, sa.permissions, m)
        self.assertNotIn("billing_settings", Role.objects.get(slug="read_only").permissions)


class RateLimitAndBots(BillingBase):
    def test_public_actions_are_rate_limited(self):
        inv = issued()
        codes = [self.client.post(inv.public_path, {"action": "report_payment", "reference": f"R{i}", "amount": "1"}).status_code for i in range(13)]
        self.assertEqual(codes[-1], 429)

    def test_bots_do_not_count_as_views(self):
        inv = issued()
        self.client.get(inv.public_path, HTTP_USER_AGENT="Googlebot/2.1")
        inv.refresh_from_db()
        self.assertEqual(inv.view_count, 0)
        self.client.get(inv.public_path, HTTP_USER_AGENT="Mozilla/5.0 Chrome")
        inv.refresh_from_db()
        self.assertEqual(inv.view_count, 1)


class DashboardScreens(BillingBase):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_every_billing_screen_renders(self):
        inv = issued(client_email="c@x.test")
        d = draft()
        p = S.record_payment(inv, None, method=self.bank, amount=D("25"))
        done = S.record_payment(inv, None, method=self.bank, amount=D("25"), reference="Z", verify=True, verification_note="ok")
        pages = [("invoices", []), ("invoice_new", []), ("invoice_detail", [inv.pk]), ("invoice_detail", [d.pk]), ("invoice_edit", [d.pk]), ("invoice_send", [inv.pk]),
                 ("payments", []), ("payment_detail", [p.pk]), ("payment_detail", [done.pk]), ("billing_reports", []), ("billing_settings", []), ("billing_methods", []),
                 ("billing_method_new", []), ("billing_method_edit", [self.bank.pk]), ("company_profile", [])]
        for name, args in pages:
            r = self.client.get(reverse(f"dashboard:{name}", args=args))
            self.assertEqual(r.status_code, 200, name)
        for kind in ("bank_pk", "ibft", "raast", "wire", "stripe", "paypal", "payoneer", "link", "other"):
            self.assertEqual(self.client.get(reverse("dashboard:billing_method_new") + f"?kind={kind}").status_code, 200, kind)
        for k in emails.KINDS:
            self.assertEqual(self.client.get(reverse("dashboard:invoice_send", args=[inv.pk]) + f"?kind={k}").status_code, 200, k)
        for qs in ("?status=overdue", "?status=paid", "?q=Khan&currency=USD", "?method=bank_pk", "?from=2026-01-01&to=2026-12-31", "?client=ayesha"):
            self.assertEqual(self.client.get(reverse("dashboard:invoices") + qs).status_code, 200, qs)
        for st in ("pending", "confirmed", "all"):
            self.assertEqual(self.client.get(reverse("dashboard:payments") + f"?status={st}").status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:payments_export")).status_code, 200)

    def test_sidebar_has_a_billing_group(self):
        r = self.client.get(reverse("dashboard:invoices"))
        for label in ("Invoices", "Payments", "Company billing", "Payment methods", "Company profile PDF"):
            self.assertContains(r, label)

    def test_page_has_viewport_meta_and_responsive_editor_rules(self):
        r = self.client.get(reverse("dashboard:invoice_new"))
        self.assertContains(r, "viewport")
        self.assertContains(r, "@media(max-width:1000px)")
        pub = self.client.get(issued().public_path)
        self.assertContains(pub, "width=device-width")

    def test_create_save_draft_then_issue_through_the_dashboard(self):
        post = {"client_name": "Zed Corp", "client_email": "zed@client.test", "currency": "USD", "billing_type": "full", "discount": "0", "tax_percent": "0", "project_name": "SEO",
                "item_desc": ["Audit", "Fixes"], "item_detail": ["", ""], "item_qty": ["1", "2"], "item_price": ["100", "50.50"], "item_unit": ["", "hrs"]}
        r = self.client.post(reverse("dashboard:invoice_new"), post)
        inv = Invoice.objects.get(client_name="Zed Corp")
        self.assertRedirects(r, reverse("dashboard:invoice_detail", args=[inv.pk]))
        self.assertEqual((inv.status, inv.number, inv.total), ("draft", None, D("201.00")))
        r = self.client.post(reverse("dashboard:invoice_action", args=[inv.pk]), {"action": "issue"}, follow=True)
        self.assertContains(r, "confirmation box")
        inv.refresh_from_db()
        self.assertTrue(inv.is_draft)
        r = self.client.post(reverse("dashboard:invoice_action", args=[inv.pk]), {"action": "issue", "confirm": "yes"}, follow=True)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.ISSUED)
        self.assertEqual(EmailMessage.objects.count(), 0)  # issuing never emails by itself

    def test_server_ignores_tampered_totals_and_rejects_bad_numbers(self):
        post = {"client_name": "Zed", "currency": "USD", "billing_type": "full", "discount": "-5", "tax_percent": "150", "item_desc": ["A"], "item_qty": ["1"], "item_price": ["10"], "total": "0.01", "subtotal": "0.01"}
        r = self.client.post(reverse("dashboard:invoice_new"), post)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Invoice.objects.filter(client_name="Zed").exists())
        post.update(discount="0", tax_percent="0", item_price=["abc"])
        self.client.post(reverse("dashboard:invoice_new"), post)
        self.assertEqual(Invoice.objects.get(client_name="Zed").total, D("0.00"))

    def test_disabled_currency_is_rejected_by_the_editor(self):
        company(enabled_currencies="USD,PKR")
        post = {"client_name": "Zed", "currency": "AED", "billing_type": "full", "discount": "0", "tax_percent": "0", "item_desc": ["A"], "item_qty": ["1"], "item_price": ["10"]}
        self.client.post(reverse("dashboard:invoice_new"), post)
        self.assertFalse(Invoice.objects.filter(client_name="Zed").exists())

    def test_verification_screen_confirms_with_note_and_checkbox(self):
        inv = issued()
        p = S.record_payment(inv, None, method=self.bank, amount=D("100"))
        url = reverse("dashboard:payment_action", args=[p.pk])
        r = self.client.post(url, {"action": "confirm", "note": "ok"}, follow=True)
        self.assertContains(r, "Tick the box")
        r = self.client.post(url, {"action": "confirm", "checked": "1", "note": "HBL statement 12 Oct"}, follow=True)
        self.assertContains(r, "Receipt RCT-")
        self.assertEqual(Invoice.objects.get(pk=inv.pk).status, Invoice.PAID)

    def test_company_settings_validation_and_save(self):
        r = self.client.post(reverse("dashboard:billing_settings"), {"legal_name": "X", "enabled_currencies": "USD,XXX", "default_currency": "USD", "quotation_currency": "USD", "invoice_prefix": "in v",
                                                                     "receipt_prefix": "RCT", "brand_color": "red", "number_padding": 4, "invoice_start_number": 1, "payment_terms_days": 14,
                                                                     "registration_label": "Reg", "tax_label": "NTN", "tax_name": "Tax", "default_tax_percent": "0", "country": "Pakistan",
                                                                     "remind_before_days": 3, "remind_every_days": 7, "max_reminders": 3})
        self.assertContains(r, "Unsupported currency")
        self.assertContains(r, "Letters and digits only")
        self.assertContains(r, "colour like")

    def test_reports_keep_invoiced_collected_and_unverified_separate(self):
        a = issued(((1, "1000.00"),))
        S.record_payment(a, None, method=self.bank, amount=D("400"), reference="V", verify=True, verification_note="ok")
        S.record_payment(a, None, method=self.bank, amount=D("100"), reference="U")  # unverified
        r = self.client.get(reverse("dashboard:billing_reports"))
        usd = dict(r.context["cur"])["USD"]
        self.assertEqual((usd["invoiced"], usd["collected_net"], usd["outstanding"], usd["unverified"]), (D("1000.00"), D("400.00"), D("600.00"), D("100.00")))
