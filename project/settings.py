from __future__ import annotations

from pathlib import Path

from project.env import load_env_file


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

ENV = {}
ENV.update(load_env_file(REPO_ROOT / ".env"))
ENV.update(load_env_file(BASE_DIR / ".env"))


def env(key: str, default: str) -> str:
    return ENV.get(key, default)


SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "django-insecure-controle-ferias-dev-key-change-me",
)
DEBUG = env("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accesses.apps.AccessesConfig",
    "apps.core.apps.CoreConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.scheduler.apps.SchedulerConfig",
    "apps.block.apps.BlockConfig",
    "apps.people.apps.PeopleConfig",
    "apps.sync.apps.SyncConfig",
    "apps.passwords.apps.PasswordsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.bot.apps.BotConfig",
    "apps.totvs.apps.TotvsConfig",
    "django_q",
]

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

ROOT_URLCONF = "project.urls"

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
                "apps.core.context_processors.global_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"
ASGI_APPLICATION = "project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env(
            "DJANGO_DATABASE_PATH",
            str(BASE_DIR / "data" / "controle_ferias_django.sqlite"),
        ),
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "login"

DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
PENDING_SYNC_CSV = DATA_DIR / "pendencias_sync_ferias.csv"
DEFAULT_ACCESS_SYSTEMS = ["AD PRIN", "VPN", "Gmail", "Admin", "Metrics", "TOTVS"]
GOOGLE_SHEETS_URL = env(
    "GOOGLE_SHEETS_URL",
    "https://docs.google.com/spreadsheets/d/1oIgONGE3W7E1sFFNWun3bUY6Ys3JVSK1/edit",
)

Q_CLUSTER = {
    "name": "controle_ferias",
    "workers": 2,
    "recycle": 500,
    "timeout": 300,
    "retry": 360,
    "compress": True,
    "save_limit": 250,
    "queue_limit": 500,
    "cpu_affinity": 1,
    "label": "Django Q2",
    "orm": "default",
}

# Screenshot do dashboard (Playwright)
DASHBOARD_SCREENSHOT_TOKEN = env(
    "DASHBOARD_SCREENSHOT_TOKEN",
    "troca-esse-token-secreto-agora",
)
DASHBOARD_SCREENSHOT_BASE_URL = env(
    "DASHBOARD_SCREENSHOT_BASE_URL",
    "http://127.0.0.1:8000",
)

# ── Bot WhatsApp ──────────────────────────────────────────────────────────────
# JID do grupo autorizado. Só mensagens desse grupo serão processadas.
# Deixe vazio para aceitar de qualquer origem (não recomendado).
BOT_ALLOWED_GROUP = env("BOT_ALLOWED_GROUP", "120363423378738083@g.us")
