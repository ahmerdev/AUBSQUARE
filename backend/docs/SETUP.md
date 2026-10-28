# Setup guide (local)

## 1. Requirements
Python 3.11+ (developed on 3.13), Node 18+ for the React site. PostgreSQL is optional locally – SQLite is used by default.

## 2. Backend
```powershell
cd backend
python -m venv venv ; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env`. For local work set `DJANGO_DEBUG=True` (the app refuses to start with `DEBUG=False` and no `DJANGO_SECRET_KEY`, on purpose).
Generate the encryption key used for saved e-mail/AI credentials:
```powershell
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```
and paste it as `FIELD_ENCRYPTION_KEY`. Keep a copy somewhere safe – without it, saved SMTP/IMAP/AI passwords must be re-entered.

```powershell
python manage.py migrate
python manage.py import_frontend_content     # safe to re-run: it only fills empty tables
python manage.py createsuperuser
```
No admin account exists until you create one. There is no public set-up page and no default password.
Alternative for scripts: set `AUB_ADMIN_EMAIL` and `AUB_ADMIN_PASSWORD` and run `python manage.py bootstrap_admin` (then remove the password variable).

## 3. Run
Option A – one server (what production looks like): build the site once, Django serves it.
```powershell
cd ..        # project root
npm install
npm run build
cd backend
python manage.py runserver
```
Open <http://127.0.0.1:8000/>. Rebuild (`npm run build`) after changing React code.

Option B – hot reload while editing React: run `python manage.py runserver` in `backend` and `npm run dev` in the project root.
The Vite dev server (port 3000) forwards `/api` and `/media` to Django on port 8000 (override with `VITE_BACKEND_URL`).
If Django is not running, the React site still opens and shows the original built-in content (offline fallback).

## 4. First steps in the dashboard
1. **Site settings** – name, contact e-mail, WhatsApp number, social links, footer text, cookie notice.
2. **Home page builder** – drag/reorder sections, hide them, edit their text.
3. **Roles & Users** – invite team members. New self-registrations stay *Pending* until a Super Admin approves them; Rejected/Suspended users cannot sign in.
4. **Email settings** – choose Gmail / Workspace / Outlook / Microsoft 365 / custom SMTP. Credentials are stored encrypted. Nothing is sent until you press **Send test email**.
   Gmail/Workspace/Outlook need an *app password* or an admin-enabled SMTP/IMAP account; normal passwords are usually refused by the provider.
5. **Chatbot** – knowledge base entries, quick replies, hand-off. The bot answers from your FAQs, services and knowledge base. AI replies are only used if you add a provider key and switch it on; otherwise the chat widget says it is an automated assistant.
6. **SEO** – per-page titles/descriptions, redirects, sitemap, audits.

## 5. Background jobs (run by hand, Windows Task Scheduler or cron)
| Command | Purpose | Suggested interval |
| --- | --- | --- |
| `python manage.py process_email_queue` | sends queued mail, retries failures with back-off | every 1–5 min |
| `python manage.py sync_inbox` | pulls new mail from the configured IMAP inbox | every 5–10 min |
| `python manage.py send_scheduled_campaigns` | sends e-mail campaigns whose scheduled time has arrived | every 5 min |
| `python manage.py run_outreach` | Outbound Sales: audits waiting prospects, moves approved outreach into the mail queue (respecting the daily limit), advances follow-up steps, stops sequences on replies, checks slow-to-answer leads and proposal reminders | every 10–15 min |

## 5b. Outbound Sales, free audit and proposals (new)
Open **Dashboard → Outbound Sales**. First visit *Outbound settings* and fill in your **postal address** (required in every cold-email footer), sender name, allowed countries and daily limit (default 30). Nothing is ever sent until a person approves it in *Outreach*, and SMTP must be configured (*Email settings*).
* **Find prospects** – search OpenStreetMap by business type and city, or import a CSV (max 500 rows). Only real businesses are added; nothing is invented. Prospects are separate from Leads until you press **Lead banao**.
* **Audit** – each prospect's website is fetched safely (public addresses only, ports 80/443) and scored. If a site cannot be reached no score is shown.
* **AI pitch (optional)** – paste a Gemini API key in *Outbound settings*; it is stored encrypted and never shown again. Without a key a clearly labelled template is used.
* **Public free audit** – `/free-audit` on the website. Limits: `FREE_AUDIT_DAILY_CAP` (default 80 per day), `THROTTLE_AUDIT` and `THROTTLE_AUDIT_LEAD` (default 6/hour per visitor). A visitor becomes a Lead only after ticking the consent box.
* **Speed-to-lead** – new leads that wait longer than the configured minutes alert staff. Automatic first reply is **off** by default and only goes to people who gave consent.
* **Proposals** – build from a Lead or Prospect, send by e-mail or share the private `/p/<token>/` link. Staff are alerted when it is opened. A client pressing *Yes, I'd like to go ahead* only records a request; you confirm *Won* yourself. Prices are in USD.
* **Search by country and city** – the *Find businesses* card and the prospect form have a searchable country list (≈250 countries) with that country's cities (`static/dashboard/geo.json`, works offline). Pick a business type, a country, a city and how many; the search never invents rows.
* **What the prospect receives** – every approved e-mail gets, added by the system (not the AI): a link to their private **audit report** `/r/<token>/` (if the site was audited), a link to your portfolio, a link to your website, your postal address and a one-click unsubscribe. Turn each link on/off in *Outbound settings → What is attached to every email*. **Set `SITE_URL` in `.env` to your real public address** (not localhost) or these links will not open for recipients; *Outbound overview* warns you while it is still localhost. *Outreach* has “See exactly what the prospect will receive” before you approve.
* **Audit report page** – `/r/<token>/` is private (noindex, not in the sitemap). Staff use *Open report* / *Copy link* on the prospect page. The first time a real person opens it you get a notification and a note. It shows a **health score (100 = best)**; the sales-side *opportunity score* on the prospect page (higher = more to sell) is never shown to the prospect.
* After updating run `python manage.py migrate` (adds outbound migration 0004) and `npm run build`, then restart Django.
* **Importing the old LeadRadar database** (optional): `python manage.py import_leadradar --db <path-to-old-sqlite> --dry-run` first to preview, then run it again without `--dry-run`. Only real OSM/website rows are imported.
* Replies that say STOP/unsubscribe, bounces and the `/o/<token>/` unsubscribe link add the business to *Do-not-contact* automatically. For replies to be detected, turn on inbox sync (IMAP).

## 5c. Billing (new)
Run `pip install -r requirements.txt` (adds reportlab, requests) and `python manage.py migrate`. Configure Billing → Company billing and Payment methods first. See `docs/BILLING.md` (Stripe env vars, webhook URL, go-live checklist). The visitor confirmation email is now ON by default (Outbound settings → Speed to lead) and only goes to visitors who gave consent.

## 6. Troubleshooting
* *"Frontend not built"* at `/` – run `npm run build` in the project root, or set `FRONTEND_DIST`.
* *Static files missing in the dashboard with DEBUG=False* – run `python manage.py collectstatic`.
* *Cannot sign in* – the account must be **Approved**; after 5 wrong passwords the account/IP is locked for a while.
