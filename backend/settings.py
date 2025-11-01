from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from django.contrib.messages import constants as messages

# ---------------- Paths ----------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------- Environment ----------------
ENV = os.getenv("ENV", "local")
env_file = BASE_DIR / (".env.production" if ENV == "production" else ".env.local")

if env_file.exists():
    load_dotenv(env_file)
    print(f"🧩 Loaded environment file: {env_file.name}")
else:
    print("⚠️ No .env file found — using system environment variables")

# ---------------- Core Settings ----------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ---------------- Hosts ----------------
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,0.0.0.0,finsecure-jgzx.onrender.com"
    ).split(",")
]

CSRF_TRUSTED_ORIGINS = [
    f"http://{h}" if DEBUG else f"https://{h}"
    for h in ALLOWED_HOSTS
    if not h.startswith("127.") and not h.startswith("localhost")
]

print(f"✅ ALLOWED_HOSTS = {ALLOWED_HOSTS}")
print(f"✅ CSRF_TRUSTED_ORIGINS = {CSRF_TRUSTED_ORIGINS}")

# ---------------- Installed Apps ----------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.humanize',
    "social_django",
    "django_q",
    "users",
    "assistance",
    "emails",
    "transactions",
]

# ---------------- Middleware ----------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

# ---------------- Templates ----------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",

            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# ---------------- Database ----------------
if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    print("🛢️  Using SQLite (Local Development)")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
    print("🛢️  Using PostgreSQL (Production)")

# ---------------- Authentication ----------------
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/users/dashboard/"
LOGOUT_REDIRECT_URL = "/users/login/"

AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------- Email (SendGrid) ----------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = os.getenv("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "finsecure7@gmail.com")

# ---------------- Google OAuth ----------------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = GOOGLE_CLIENT_ID
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = GOOGLE_CLIENT_SECRET

# ---------------- 🔒 Gmail Token Storage ----------------
# Local directory to store Gmail OAuth tokens safely
TOKENS_DIR = BASE_DIR / "tokens"
os.makedirs(TOKENS_DIR, exist_ok=True)

# Full path for credentials.json (Google Client Secrets)
GOOGLE_CREDENTIALS_FILE = BASE_DIR / "credentials.json"

print(f"📁 Gmail Tokens Directory: {TOKENS_DIR}")
print(f"🔐 Google Credentials Path: {GOOGLE_CREDENTIALS_FILE}")

# ---------------- Static & Media ----------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------- Internationalization ----------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# ---------------- Password Validators ----------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------- Logging ----------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---------------- Security ----------------
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    print("⚙️  Running in DEBUG mode - HTTP only")
else:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    print("🔒 Running in PRODUCTION mode - HTTPS enforced")

# ---------------- Misc ----------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True

MESSAGE_TAGS = {
    messages.DEBUG: "debug",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

# ---------------- Django Q ----------------
Q_CLUSTER = {
    "name": "FinSecureQ",
    "workers": 4,
    "recycle": 500,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "orm": "default",
}

# ---------------- Cache ----------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "otp_cache",
    }
}
