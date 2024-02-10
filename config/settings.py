from pathlib import Path

import environs
from django.contrib.messages import constants as message_constants

env = environs.Env()
env.read_env()

DEBUG = env.bool("DEBUG", default=True)
BASE_DIR = Path(__file__).resolve().parent.parent
# SECRET_KEY must be specified in production environments.
SECRET_KEY = env.str(
    "SECRET_KEY",
    default=(
        "django-insecure 43)%4yx)aa@a=+_c(fn&kf3g29xax+=+a&key9i=!98zyim=8j"
        if DEBUG
        else None
    ),
)
HOST_PORT = env.str("HOST_PORT", default="")
ALLOWED_HOSTS = []
DJANGO_HOSTNAME = env.str("DJANGO_HOSTNAME", default=None)
if DJANGO_HOSTNAME:
    ALLOWED_HOSTS += [DJANGO_HOSTNAME]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "0.0.0.0", "127.0.0.1"]  # nosec
    INTERNAL_IPS = ["127.0.0.1"]

# In production we may use a different URL for the admin interface.
ADMIN_URL = env.str("ADMIN_URL", default="admin/")
SITE_ID = 1
SITE_TITLE = env.str("SITE_TITLE", default="Campaign Manager")
GAME_ID = env.int("GAME_ID", default=1)
LANGUAGE_CODE = "en-us"
TIME_ZONE = env.str("TIME_ZONE", default="UTC")
USE_TZ = True

# Security settings
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.flatpages",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "crispy_forms",
    "crispy_bootstrap5",
    "debug_toolbar",
    "rules.apps.AutodiscoverRulesConfig",
    "django_htmx",
    "django_celery_results",
    # Social auth providers. See here for the full available list:
    # https://django-allauth.readthedocs.io/en/latest/installation.html
    "allauth.socialaccount.providers.discord",
    "allauth.socialaccount.providers.google",
    # Local
    "camp.accounts",
    "camp.game",
    "camp.character",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "camp.context.CurrentGameMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "debug": DEBUG,
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "camp.context.settings",
                "camp.context.game",
            ],
        },
    },
]

DATABASES = {
    "default": env.dj_db_url(
        "DATABASE_URL",
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        ssl_require=not DEBUG,
    )
}

REDIS_URL = env.str(
    "REDIS_URL" if DEBUG else "REDIS_TLS_URL", default="redis://localhost:6379/0"
)


AUTHENTICATION_BACKENDS = (
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(BASE_DIR / "static")]
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Parse email URLs, e.g. "smtp://"
# See https://github.com/migonzalvar/dj-email-url/blob/master/README.rst for syntax
email_config = env.dj_email_url("EMAIL_URL", default="console:")
EMAIL_FILE_PATH = email_config["EMAIL_FILE_PATH"]
EMAIL_HOST_USER = email_config["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = email_config["EMAIL_HOST_PASSWORD"]
EMAIL_HOST = email_config["EMAIL_HOST"]
EMAIL_PORT = email_config["EMAIL_PORT"]
EMAIL_BACKEND = email_config["EMAIL_BACKEND"]
EMAIL_USE_TLS = email_config["EMAIL_USE_TLS"]
EMAIL_USE_SSL = email_config["EMAIL_USE_SSL"]
EMAIL_TIMEOUT = email_config["EMAIL_TIMEOUT"]
SERVER_EMAIL = email_config.get("SERVER_EMAIL", "root@localhost")
DEFAULT_FROM_EMAIL = email_config.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")

EMAIL_SUBJECT_PREFIX = env.str("EMAIL_SUBJECT_PREFIX", "[Django] ")

# THIRD PARTY APP CONFIGS

# crispy_forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# allauth
LOGIN_REDIRECT_URL = "home"
# Account creation adapters
ACCOUNT_ADAPTER = "camp.accounts.adapter.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "camp.accounts.adapter.SocialAccountAdapter"
# Login using either username or email address
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
# Requires an email be provided at signup if true
ACCOUNT_EMAIL_REQUIRED = False  # Let's see if all our social auths provide this
# Require verification? 'mandatory' = no login until confirmed... maybe later.
ACCOUNT_EMAIL_VERIFICATION = "optional"
# Usernames are stored lowercase
ACCOUNT_PRESERVE_USERNAME_CASING = False
# Only ask for the password once. Use password reset if you fail.
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
# TODO: Rate limiting requires a cache other than DummyCache. Ensure we have that set up.
ACCOUNT_RATE_LIMITS = {
    # Change password view (for users already logged in)
    "change_password": "5/m",
    # Email management (e.g. add, remove, change primary)
    "manage_email": "10/m",
    # Request a password reset, global rate limit per IP
    "reset_password": "20/m",
    # Rate limit measured per individual email address
    "reset_password_email": "5/m",
    # Password reset (the view the password reset email links to).
    "reset_password_from_key": "20/m",
    # Signups.
    "signup": "20/m",
    # NOTE: Login is already protected via `ACCOUNT_LOGIN_ATTEMPTS_LIMIT`
}
ACCOUNT_SIGNUP_ENABLED = env.bool("SIGNUP_ENABLED", default=True)

MESSAGE_TAGS = {
    message_constants.DEBUG: "primary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

UNDO_STACK_SIZE = env.int("UNDO_STACK_SIZE", default=10)

# Should we include hx-boost="true"? Debugging may be easier with it off.
ENABLE_HXBOOST = env.bool("ENABLE_HXBOOST", default=False)

DEBUG_TOOLBAR_CONFIG = {"ROOT_TAG_EXTRA_ATTRS": "hx-preserve"}


# Celery task queue
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TASK_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SOFT_TIME_LIMIT = env.int("TASK_SOFT_TIMEOUT_SECONDS", default=3600)
CELERY_TASK_TIME_LIMIT = env.int("TASK_HARD_TIMEOUT_SECONDS", default=3600 * 2)


# Sentry error reporting
if sentry_dsn := env.str("SENTRY_DSN", default=None):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    if traces_sample_rate := env.float("SENTRY_SAMPLE_RATE", default=None):
        if traces_sample_rate < 0:
            traces_sample_rate = 0.0
        if traces_sample_rate > 1:
            traces_sample_rate = 1.0

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=traces_sample_rate,
    )
