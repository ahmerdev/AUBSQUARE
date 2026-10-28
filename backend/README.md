# AUB SQUARE – Django backend, CMS & admin dashboard

This folder adds a real backend to the React site in the parent folder:

* **REST API** (`/api/v1/…`, Django REST Framework) that the React site reads. Only *published* content is ever public.
* **Admin dashboard** (`/dashboard/`) – responsive control centre with a Light/Dark switch to edit every part of the site, manage leads, email, chat, SEO, marketing, users and roles.
* **Server-rendered SEO**: the built React `index.html` is served by Django with the right `<title>`, description, canonical, Open Graph, JSON-LD and crawlable text for every route, plus `sitemap.xml` and `robots.txt`.

```
AUBSQUARE/            React + Vite + Tailwind site (src/, package.json)
  backend/            Django project (this folder)
    apps/             accounts, core, cms, blog, leads, mailer, chatbot, seo, marketing, analytics, api, dashboard, tests
    config/           settings, urls
    docs/             SETUP, DEPLOYMENT, BACKUP, SECURITY, TESTING
```

## Quick start (Windows PowerShell, from the `backend` folder)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit .env (DJANGO_DEBUG=True for local work)
python manage.py migrate                   # also applies 0002_brand_fonts (Branding fonts + header option)
python manage.py import_frontend_content   # one-time: loads the current site content so the dashboard starts full
python manage.py createsuperuser           # your own admin e-mail + password – nothing is pre-created
python manage.py runserver
```

Open <http://127.0.0.1:8000/dashboard/> and sign in. Full steps, including running the React dev server next to Django, are in [docs/SETUP.md](docs/SETUP.md).

## Documents

| File | What it covers |
| --- | --- |
| [docs/SETUP.md](docs/SETUP.md) | Local installation, first admin, dev workflow, e-mail / chat / AI settings |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production checklist (PostgreSQL, gunicorn, HTTPS, static/media, cron jobs) |
| [docs/BACKUP.md](docs/BACKUP.md) | What to back up and how to restore |
| [docs/SECURITY.md](docs/SECURITY.md) | Security design and what you must still do |
| [docs/TESTING.md](docs/TESTING.md) | What is covered by automated tests, what was checked by hand, **what was not tested** |
