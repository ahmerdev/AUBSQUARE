# Security notes

**Built in**
* Staff sign in with e-mail + password; passwords hashed by Django (PBKDF2), validators enforced. Account **status** (Pending / Approved / Rejected / Suspended) is checked on every login *and* on every request, so suspending someone ends their session immediately. Password change/reset invalidates other sessions.
* Brute-force protection: failed-login counter with temporary lockout per account and per IP.
* Password reset: single-use, expiring, hashed tokens; the response is identical whether or not the e-mail exists. Invitations use the same token scheme.
* Roles with per-module permissions (view/create/edit/delete/…) enforced on the server for every dashboard view and action; the menu only hides what you cannot use.
* CSRF on all dashboard forms; same-origin session cookies; `HttpOnly`, `Secure` and HSTS in production.
* Public API is read-only except: quote/contact form, comments, newsletter, chat, page-view. These have rate limits, a honeypot field, a signed time-stamped form token (instant bot submissions are quarantined), duplicate detection, length limits and plain-text cleaning.
* Rich text (blog, pages) is sanitised with an allow-list (nh3) on save; links get `rel="noopener"`; scripts, inline event handlers and `javascript:` URLs are removed.
* Uploads: extension allow-list (no SVG/HTML/executables), size limit, content sniffing, Pillow verification and re-encode (EXIF/metadata dropped) for images.
* Integration secrets (SMTP/IMAP passwords, AI keys) are encrypted at rest with `FIELD_ENCRYPTION_KEY`, are never sent back to the browser (the form shows “saved”) and are never placed in the React bundle.
* CSV exports neutralise spreadsheet formulas (`=`, `+`, `-`, `@`).
* Analytics are privacy-friendly: no IP stored, daily-rotating hashed visitor id, Do-Not-Track / Global-Privacy-Control respected, bots skipped.
* Every important change (login, user/role changes, settings, content publish, exports, deletes) is written to the activity log.
* The dashboard is `noindex` and disallowed in `robots.txt`.

**You still need to**
* Use HTTPS, keep `DJANGO_DEBUG=False`, set a strong `DJANGO_SECRET_KEY`, and never commit `.env`.
* Keep Django and dependencies updated (`pip list --outdated`), and run `python manage.py check --deploy`.
* Keep the number of Super Admins small; give everyone else the narrowest role.
* Back up `FIELD_ENCRYPTION_KEY` separately.
* Have your own privacy policy / consent wording reviewed for the countries you serve; the cookie notice and consent checkboxes are tools, not legal advice.
* This code has **not** had an independent security audit or penetration test.
