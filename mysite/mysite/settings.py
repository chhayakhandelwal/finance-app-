from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers
from celery.schedules import crontab
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
# ----------------------------
# Base
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-8w_ig4+@63x$&^_)q87wz5j=ey(6&q$x36bu9fj3fc(xrgpnue"
DEBUG = True

# ----------------------------
# Applications
# ----------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",
    # Local
    "core.apps.CoreConfig",
]

AUTH_USER_MODEL = "core.AppUser"

# ----------------------------
# Middleware (ORDER IS CRITICAL)
# ----------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # MUST be first
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "mysite.urls"
# Email (DEV) — prints emails in terminal


# ----------------------------
# Templates
# ----------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

# ----------------------------
# Database (PostgreSQL)
# ----------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {
            "sslmode": "require",
        },
    }
}

# ----------------------------
# Password Validation
# ----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----------------------------
# CORS SETTINGS (FIXED)
# ----------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:3001",
    "http://127.0.0.1:3001",

    "http://localhost:3002",      # ✅ FIX (YOUR CURRENT FRONTEND)
    "http://127.0.0.1:3002",

    "http://localhost:3003",
    "http://127.0.0.1:3003",

    "http://localhost:5173",
    "http://127.0.0.1:5173",

    "http://localhost:3006",
    "http://127.0.0.1:3006",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = list(default_headers) + [
    "authorization",
    "content-type",
    "x-csrftoken",
]
# ----------------------------
# CSRF TRUSTED ORIGINS (FIXED)
# ----------------------------
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:3001",
    "http://127.0.0.1:3001",

    "http://localhost:3002",      # ✅ FIX
    "http://127.0.0.1:3002",

    "http://localhost:3003",
    "http://127.0.0.1:3003",

    "http://localhost:5173",
    "http://127.0.0.1:5173",

    "http://localhost:3006",
    "http://127.0.0.1:3006",
]

# ----------------------------
# Django REST Framework
# ----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# ----------------------------
# Simple JWT
# ----------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ----------------------------
# Internationalization
# ----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ----------------------------
# Static
# ----------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"




EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 20

EMAIL_HOST_USER = "rishikaa11aa@gmail.com"

#import os
EMAIL_HOST_PASSWORD = "chdbrmdzcjfpuwbi"

DEFAULT_FROM_EMAIL = f"Django Finance <rishikaa11aa@gmail.com>"



CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_TIMEZONE = "Asia/Kolkata"

CELERY_BEAT_SCHEDULE = {
    # Every day 9 AM: deadline reminders (30/15/5 days before)
    "daily-deadline-reminders": {
        "task": "core.tasks.daily_deadline_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    # New (28–31 daily at 9 PM, task month-end check karega)
    "monthly-no-contribution-month-end": {
    "task": "core.tasks.month_end_no_contribution_alert",
    "schedule": crontab(day_of_month="28-31", hour=21, minute=0),  # 9:00 PM
    },

    "daily-emergency-interval-check": {
        "task": "core.tasks.daily_emergency_interval_check",
        "schedule": crontab(hour=9, minute=30),  # 9 PM IST
    },
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mfapi-cache",
        "TIMEOUT": 60 * 60 * 12,  # 12 hours
    }
}

#-------monthly summary-------

import os

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],   # ← THIS MUST BE PRESENT
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]