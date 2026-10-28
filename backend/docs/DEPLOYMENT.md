# Production deployment checklist

1. **Server**: any Linux VPS or PaaS with Python 3.11+. Put nginx/Caddy (or the platform's router) in front for HTTPS.
2. **Environment** (never commit): copy `.env.example` → `.env`.
   * `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `SITE_URL`, `CSRF_TRUSTED_ORIGINS`.
   * `FIELD_ENCRYPTION_KEY` (Fernet) and `VISITOR_HASH_SALT`.
   * `TRUST_X_FORWARDED_FOR=True` **only** if your reverse proxy sets/overwrites `X-Forwarded-For`; otherwise rate limits and lockouts see the proxy's IP.
3. **Database**: PostgreSQL. `DB_ENGINE=postgres` + `DB_NAME/USER/PASSWORD/HOST/PORT`. `pip install -r requirements.txt` already includes `psycopg`.
4. **Build the site**: `npm ci && npm run build` (creates `dist/`), set `FRONTEND_DIST` if it is not at `../dist`.
5. **Prepare Django**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py import_frontend_content      # first deploy only
   python manage.py bootstrap_admin               # with AUB_ADMIN_EMAIL / AUB_ADMIN_PASSWORD set once, then unset
   python manage.py check --deploy
   ```
6. **Run**: `gunicorn config.wsgi:application --workers 3 --bind 127.0.0.1:8000` under systemd/supervisor. WhiteNoise serves static files and the built site assets.
7. **Media uploads** live in `MEDIA_ROOT`. Let nginx/CDN serve `/media/`, or set `SERVE_MEDIA=True` for small sites. Back this folder up.
8. **Cron / scheduled tasks**: the three commands in SETUP.md §5.
9. **After deploy**: sign in, change nothing else first – open *Site settings*, *Email settings* (send a test mail), submit a test quote request, check *Leads*, and confirm `/sitemap.xml` and `/robots.txt`.
10. **Search consoles**: add your verification codes in *SEO → Site verification*, then submit `/sitemap.xml`.

Security headers (HSTS, secure cookies, SSL redirect) switch on automatically when `DJANGO_DEBUG=False`. Terminate TLS before Django.
