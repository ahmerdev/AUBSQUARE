# Backup and restore

Back up **three** things, together, on a schedule you can live with (daily is typical):
1. **Database** – PostgreSQL: `pg_dump -Fc aubsquare > aubsquare_$(date +%F).dump`. SQLite: copy `db.sqlite3` while the site is stopped (or use `sqlite3 db.sqlite3 ".backup backup.sqlite3"`).
2. **Uploaded media** – the whole `MEDIA_ROOT` folder.
3. **Your `.env`** – store it separately in a password manager, **especially `FIELD_ENCRYPTION_KEY`**. Without that key the saved SMTP/IMAP/AI credentials cannot be decrypted (you would simply re-enter them).

Restore: install the same app version, restore `.env`, restore the database (`pg_restore -d aubsquare file.dump`), restore `MEDIA_ROOT`, run `python manage.py migrate`, then `collectstatic`.
Test a restore on a spare machine at least once – an untested backup is only a hope.

Content can also be exported from the dashboard (leads / subscribers CSV). Those exports contain personal data: store and share them accordingly.
