# Billing, invoices & payments

Everything lives in the `apps/billing` app and the **Billing** group of the dashboard menu. It extends the existing Media Library, Mailer, Proposals and Permissions — nothing was duplicated.

## 1. What you configure (admin, once)

| Where | What |
|---|---|
| Billing → **Company billing** | Legal / trading name, logo (pick from Media Library), address, registration & tax labels/numbers (labels are free text, so they work for any country), default tax %, default & enabled currencies, payment terms, invoice/receipt prefix, start number, padding, yearly reset, footer, notes, signatory, brand colour, reminder rules |
| Billing → **Payment methods** | Bank transfer (PKR), IBFT, Raast, SWIFT/international wire, card gateways (Stripe), PayPal/Payoneer *payment-link* methods, other. Each has its own details, accepted currencies and a reference format such as `{invoice}` |
| Billing → **Company profile PDF** | Choose a PDF **that is already in the Media Library** (upload it there once). Replacing creates a new version; old versions stay |

Billing settings and payment methods are protected by their own permissions (`billing_settings`, `payments`).

## 2. Day-to-day flow

1. Proposal marked **Won** → *Create draft invoice* (full / deposit % / final / milestone). Or *Invoices → New invoice* for a manual one. Nothing is sent.
2. Review the draft (live preview, totals recomputed on the server — the browser's totals are never trusted).
3. **Issue** (tick the confirmation box). The invoice gets its number, and a snapshot of your company details and payment methods is frozen onto it. Later changes to settings never alter an issued invoice.
4. **Send to client**: editable preview of the email, PDF attached, optional company-profile PDF (attach / secure link / none). Sending is always a deliberate click.
5. Client pays → you **record** the payment. It stays **Pending** until someone with the *verify* permission confirms it, tying it to a bank statement line. A screenshot or a client's "I've paid" message never marks anything paid.
6. Confirm → status moves to *Partially paid* / *Paid*, a receipt number is assigned, the receipt PDF can be emailed.

Statuses: Draft · Issued · Sent · Partially paid · Paid · Cancelled · Void. **Overdue** is calculated from the due date and the balance (never stored, so it cannot go stale).

Corrections: an issued invoice cannot be edited. *Revise* voids it (number kept, never recycled) and opens a linked corrected draft. Cancel/void needs a reason and is blocked once money was received — refund it first. There is no separate credit-note document (see limitations).

## 3. Payments in Pakistan

Bank transfer, IBFT and Raast are first-class: configure account title, bank, account number/IBAN, Raast ID and instructions. The client page and the email show them with the exact reference to use. Payments are **offline & manual**: recorded as pending, verified by a person.

International clients: the **SWIFT wire** method records currency, the received amount, the exchange rate your bank really used and the bank fee. Rates are never guessed.

## 4. Online gateways — honest status

| Provider | Status for a Pakistan-based business | What the code does |
|---|---|---|
| **Stripe** | Pakistan is **not** on Stripe's supported-country list (https://stripe.com/global). Do **not** enable unless you hold a legitimately approved account (e.g. through an eligible entity). | Full adapter (hosted Checkout, signature-verified webhooks, refunds). **Off** unless you tick "I confirm eligibility" **and** the env secrets exist. Not tested against live Stripe from the build sandbox. |
| **PayPal** | PayPal does not offer normal receiving accounts in Pakistan; a freelancer scheme announced in 2024 was not confirmed live. | Only a manual "payment link you create" method; no API integration. |
| **Payoneer** | Payment requests (client pays by card/bank, funds to your linked bank, KYC required). | Manual "payment link" method; no API integration. |

Whether a method is *allowed for you* is a legal/account decision. The software only refuses to show a gateway that is disabled, un-confirmed or missing secrets.

### Stripe setup (only if eligible)
Environment variables (never stored in the database):

```
STRIPE_SECRET_KEY_TEST=sk_test_...
STRIPE_WEBHOOK_SECRET_TEST=whsec_...
STRIPE_SECRET_KEY_LIVE=sk_live_...
STRIPE_WEBHOOK_SECRET_LIVE=whsec_...
```

Create the method in *Payment methods* (mode **test** first), set the Stripe dashboard webhook to `https://YOUR-DOMAIN/billing/webhooks/stripe/` with events `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `payment_intent.payment_failed`, `charge.refunded`. Webhooks are verified (HMAC-SHA256, 5-minute tolerance), idempotent (unique event id) and amount/currency are re-checked: a mismatch is held as *Pending* for a human instead of being auto-confirmed. Card data never touches this server. Returning from the checkout page does **not** mark anything paid; only the verified webhook does.

## 5. Permissions

`invoices` (view/create/edit/approve=issue/delete=void-cancel), `payments` (view/create=record/approve=verify/edit=refund), `billing_reports`, `billing_settings`. Sales managers can draft and send but not issue, verify, refund or see bank settings. Read-only staff can view invoices only. Public invoice links use 28+ character random tokens, are `noindex`, `no-store`, rate-limited, and a receipt link only works with its own invoice's token.

## 6. Emails

Types: issued, due soon, reminder, overdue, payment received (receipt attached), payment failed, refund, cancelled/void. Plain-text for deliverability. The status is worded honestly: **"Accepted by mail server"** — not "delivered". Failures retry automatically. Reminders are **off by default** (Company billing → reminders) and are never sent for paid, closed or disputed invoices or do-not-contact addresses. Scheduled checks run with `python manage.py run_outreach` (or *Run checks now*).

## 7. Deployment

```
pip install -r requirements.txt     # adds reportlab, requests
python manage.py migrate            # accounts 0004, billing 0001, mailer 0003, outbound 0005-0006
```

PDFs use the bundled DejaVu Sans fonts in `apps/billing/fonts/` (Bitstream Vera/DejaVu licence — free to bundle; keep the licence notice with the fonts). Logos are read only from your own `MEDIA_ROOT`.

## 8. Go-live checklist

- [ ] Company billing filled in (legal name, address, tax number, footer)
- [ ] At least one real payment method with correct details; send yourself a test invoice
- [ ] Email settings tested with *Send test email*; SPF/DKIM/DMARC set on the sending domain
- [ ] Profile PDF uploaded to the Media Library and selected
- [ ] Roles reviewed (who may issue / verify / refund)
- [ ] Check an issued invoice PDF on paper/phone; confirm numbering prefix/start number matches your existing sequence
- [ ] Stripe: only if eligible — test mode end-to-end, then live
- [ ] Cron/Task Scheduler for `run_outreach`
- [ ] Back-ups on (invoices are financial records)

## 9. Known limitations

* No separate **credit-note** document (void/revise/refund instead); no recurring auto-billing; PDF text does not render Arabic/RTL shaping; reports are management reports, not financial statements; no bank-feed auto-reconciliation; raw `/media/uploads/<uuid>` URLs are unguessable but not access-controlled (the profile is shared via a switchable `/d/<token>/` link); Stripe was not exercised against the live API; tax rules are your responsibility — the system applies the % you give it.
