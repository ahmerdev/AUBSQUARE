"""
AUB SQUARE – Django settings.

All secrets / environment specific values come from environment variables (or a local
`backend/.env` file that is NEVER committed). See `backend/.env.example`.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # the React project root
load_dotenv(BASE_DIR / ".env")


def env(name: str, default=None):
    return os.environ.get(name, default)


def env_bool(name: str, default=False) -> bool:
    return str(env(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default="") -> list[str]:
    return [x.strip() for x in str(env(name, default)).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
TESTING = "test" in sys.argv

SECRET_KEY = env("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-development-only-key-do-not-use-in-production-0123456789"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set (see backend/.env.example).")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
FREE_AUDIT_DAILY_CAP = int(env("FREE_AUDIT_DAILY_CAP", "80"))  # max public audits per day across all visitors
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")  # public site origin (for sitemap, emails, canonicals)
DASHBOARD_URL_PREFIX = "dashboard"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.cms",
    "apps.blog",
    "apps.leads",
    "apps.mailer",
    "apps.chatbot",
    "apps.seo",
    "apps.marketing",
    "apps.analytics",
    "apps.outbound",
    "apps.billing",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.seo.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.dashboard.context_processors.dashboard",
            ],
        },
    },
]

# ---------------------------------------------------------------- Database
# SQLite for a zero-config local start; PostgreSQL for production (set DB_ENGINE=postgres).
if env("DB_ENGINE", "sqlite").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "aubsquare"),
            "USER": env("DB_USER", "aubsquare"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- Auth
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.ApprovedEmailBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/dashboard/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/dashboard/login/"
PASSWORD_RESET_TIMEOUT = 60 * 60  # reset links expire after 1 hour (and are single-use: token hashes the password)
LOGIN_MAX_FAILURES = int(env("LOGIN_MAX_FAILURES", 5))
LOGIN_LOCKOUT_MINUTES = int(env("LOGIN_LOCKOUT_MINUTES", 15))

SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", 60 * 60 * 12))  # 12h
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = False

# ---------------------------------------------------------------- i18n / static / media
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Asia/Karachi")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if (DEBUG or TESTING)
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MEDIA_MAX_UPLOAD_MB = int(env("MEDIA_MAX_UPLOAD_MB", 8))

# React production build served through Django's SEO-aware shell (see apps/seo/views.py)
# Optional: address of the website for the Branding live preview when it is not served by Django (e.g. http://localhost:3000).
PREVIEW_SITE_URL = env("PREVIEW_SITE_URL", "")
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(PROJECT_ROOT / "dist")))
# Serve the built React assets (/assets/*) straight from the dist folder when it exists.
if FRONTEND_DIST.exists() and not TESTING:
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = False
# Only enable behind a reverse proxy you control (nginx, Caddy, a PaaS router): rate limits and logs then see the real client IP.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)
# Serve /media/ from Django in production only when you have no web server / CDN doing it (small deployments).
SERVE_MEDIA = env_bool("SERVE_MEDIA", False)

# ---------------------------------------------------------------- CORS / CSRF
# In dev the Vite server (5173 / 3000) calls the API cross-origin. In production use the same origin.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000")
CORS_ALLOW_CREDENTIALS = False  # public API never relies on cookies
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# ---------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],  # the public API is anonymous; staff use the dashboard (session + CSRF)
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "contact": env("THROTTLE_CONTACT", "6/hour"),
        "comment": env("THROTTLE_COMMENT", "8/hour"),
        "chat": env("THROTTLE_CHAT", "90/hour"),
        "chat_start": env("THROTTLE_CHAT_START", "20/hour"),
        "pageview": env("THROTTLE_PAGEVIEW", "600/hour"),
        "unsubscribe": "30/hour",
        "audit": env("THROTTLE_AUDIT", "6/hour"),
        "audit_lead": env("THROTTLE_AUDIT_LEAD", "6/hour"),
        "public": env("THROTTLE_PUBLIC", "600/hour"),
    },
    "EXCEPTION_HANDLER": "apps.core.api.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.api.StandardPagination",
    "PAGE_SIZE": 12,
}

# ---------------------------------------------------------------- Cache
# LocMem is fine for one process. For multi-process production set REDIS_URL (django.core.cache.backends.redis).
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "aub-cache"}}

# ---------------------------------------------------------------- Email (env fallback; DB EmailSettings wins)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
if TESTING:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", 25))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "AUB SQUARE <no-reply@localhost>")
EMAIL_TIMEOUT = 20

# Key used to encrypt integration credentials stored in the DB (SMTP / IMAP / AI keys).
# Falls back to a key derived from SECRET_KEY if unset – set it explicitly in production.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")

# ---------------------------------------------------------------- Security
if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"  # the public website alone is relaxed to SAMEORIGIN (see FrontendShell) so the dashboard can show its live preview
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Salt for the daily-rotating anonymous visitor hash used by analytics / spam heuristics.
VISITOR_HASH_SALT = env("VISITOR_HASH_SALT", SECRET_KEY[:24])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}

if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
