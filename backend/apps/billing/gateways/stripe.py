"""Stripe adapter (hosted Checkout + webhooks) using Stripe's REST API directly.

Status: implemented and unit-tested with signed test payloads; it has NOT been exercised against Stripe's servers from here.
Availability: Stripe account onboarding is only offered in Stripe's supported countries (https://stripe.com/global). Pakistan is not
on that list, so keep this method switched off unless you legitimately hold an approved Stripe account.
Secrets come from environment variables only:  STRIPE_SECRET_KEY_TEST / STRIPE_WEBHOOK_SECRET_TEST  and  ..._LIVE.
"""
import hashlib
import hmac
import json
import os
import time

import requests

from .. import money
from .base import Gateway, GatewayError, WebhookResult

API = "https://api.stripe.com/v1"
TOLERANCE = 300  # seconds a webhook timestamp may differ from now (replay protection)


class StripeGateway(Gateway):
    provider = "stripe"
    label = "Stripe"

    @property
    def mode(self):
        return "live" if self.method.mode == "live" else "test"

    def _env(self, name):
        return os.environ.get(f"{name}_{self.mode.upper()}", "").strip()

    @property
    def secret_key(self):
        return self._env("STRIPE_SECRET_KEY")

    @property
    def webhook_secret(self):
        return self._env("STRIPE_WEBHOOK_SECRET")

    def missing(self):
        out = []
        if not self.secret_key:
            out.append(f"STRIPE_SECRET_KEY_{self.mode.upper()}")
        if not self.webhook_secret:
            out.append(f"STRIPE_WEBHOOK_SECRET_{self.mode.upper()}")
        return out

    def configured(self):
        return bool(self.method.verified_eligible and not self.missing())

    # -- helpers
    def _post(self, path, data):
        if not self.secret_key:
            raise GatewayError("Stripe is not configured (secret key missing).")
        try:
            r = requests.post(f"{API}{path}", data=data, headers={"Authorization": f"Bearer {self.secret_key}", "Stripe-Version": "2024-06-20"}, timeout=20)
        except requests.RequestException:
            raise GatewayError("Could not reach Stripe. Please try again in a moment.")
        try:
            js = r.json()
        except ValueError:
            raise GatewayError("Stripe returned an unreadable response.")
        if r.status_code >= 400:
            msg = (js.get("error") or {}).get("message", "Stripe rejected the request.")
            raise GatewayError(msg[:250])
        return js

    # -- checkout
    def create_checkout(self, invoice, payment, success_url, cancel_url):
        if not self.configured():
            raise GatewayError("Online card payment is not available for this invoice.")
        cur = invoice.currency.lower()
        data = {
            "mode": "payment", "success_url": success_url, "cancel_url": cancel_url, "client_reference_id": str(payment.pk),
            "line_items[0][quantity]": "1", "line_items[0][price_data][currency]": cur,
            "line_items[0][price_data][unit_amount]": str(money.minor_units(payment.amount, invoice.currency)),
            "line_items[0][price_data][product_data][name]": f"Invoice {invoice.number}"[:120],
            "metadata[payment_id]": str(payment.pk), "metadata[invoice_id]": str(invoice.pk), "metadata[invoice_number]": invoice.number or "",
            "payment_intent_data[metadata][payment_id]": str(payment.pk), "payment_intent_data[metadata][invoice_number]": invoice.number or "",
        }
        if invoice.client_email:
            data["customer_email"] = invoice.client_email
        js = self._post("/checkout/sessions", data)
        if not js.get("url") or not js.get("id"):
            raise GatewayError("Stripe did not return a checkout page.")
        payment.provider_session_id = js["id"]
        payment.save(update_fields=["provider_session_id", "updated_at"])
        return js["url"]

    # -- webhooks
    def verify_signature(self, body: bytes, header: str, now=None):
        secret = self.webhook_secret
        if not secret:
            raise GatewayError("Webhook secret is not configured.")
        parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
        # a header may carry several v1 signatures while a secret is being rolled
        sigs = [v for k, v in (p.split("=", 1) for p in (header or "").split(",") if "=" in p) if k == "v1"]
        try:
            ts = int(parts.get("t", ""))
        except ValueError:
            raise GatewayError("Invalid signature header.")
        if abs((now or time.time()) - ts) > TOLERANCE:
            raise GatewayError("Signature timestamp outside tolerance.")
        expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in sigs):
            raise GatewayError("Signature mismatch.")

    def verify_and_parse(self, body, headers):
        self.verify_signature(body, headers.get("Stripe-Signature", ""))
        try:
            ev = json.loads(body.decode("utf-8"))
        except ValueError:
            raise GatewayError("Malformed payload.")
        obj = (ev.get("data") or {}).get("object") or {}
        et = ev.get("type", "")
        res = WebhookResult(event_id=ev.get("id", ""), event_type=et, raw=ev)
        meta = obj.get("metadata") or {}
        pid = meta.get("payment_id") or obj.get("client_reference_id") or ""
        res.payment_id = int(pid) if str(pid).isdigit() else None
        if et in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            res.session_id, res.txn_id = obj.get("id", ""), obj.get("payment_intent") or obj.get("id", "")
            res.amount_minor, res.currency = obj.get("amount_total"), (obj.get("currency") or "").upper()
            res.action = "paid" if obj.get("payment_status") == "paid" else "ignore"  # unpaid = async method still pending
        elif et in ("checkout.session.async_payment_failed", "payment_intent.payment_failed"):
            res.action, res.session_id = "failed", obj.get("id", "") if et.startswith("checkout") else ""
            res.reason = ((obj.get("last_payment_error") or {}).get("message") or "Payment failed")[:250]
        elif et == "checkout.session.expired":
            res.action, res.session_id = "cancelled", obj.get("id", "")
        elif et == "charge.refunded":
            ref = ((obj.get("refunds") or {}).get("data") or [{}])[0]
            res.action, res.txn_id = "refunded", obj.get("payment_intent") or ""
            res.refund_id, res.refund_minor, res.currency = ref.get("id", ""), ref.get("amount"), (obj.get("currency") or "").upper()
            res.payment_id = None
        return res

    def refund(self, payment, amount, reason=""):
        if not payment.provider_txn_id:
            raise GatewayError("This payment has no Stripe transaction to refund.")
        js = self._post("/refunds", {"payment_intent": payment.provider_txn_id, "amount": str(money.minor_units(amount, payment.currency)), "metadata[payment_id]": str(payment.pk)})
        return {"id": js.get("id", ""), "status": js.get("status", "")}
