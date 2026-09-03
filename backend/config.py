"""Environment-based configuration for the backend API."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# SQLite locally; switch to PostgreSQL/Supabase via DATABASE_URL for deployment
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'credit_scoring.db'}")

# comma-separated list of allowed browser origins (CORS)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

# OTP simulation settings
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

# demo-only switch: return the simulated OTP in API responses so the flow can
# be demonstrated without a real SMS gateway (always clearly labelled)
DEV_RETURN_OTP = os.getenv("DEV_RETURN_OTP", "true").strip().lower() in {"1", "true", "yes", "on"}

# ---------------------------------------------------------------- Phase 1 auth

# uploaded applicant documents (CNIC images) live here; overridable so the
# test suite never writes into the real uploads directory
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", str(PROJECT_ROOT / "uploads")))

# password-reset links point at the frontend, which renders /reset-password
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")

# a reset link stays valid for this many minutes after it is issued
RESET_TOKEN_TTL_MINUTES = int(os.getenv("RESET_TOKEN_TTL_MINUTES", "30"))

# demo-only switch (mirrors DEV_RETURN_OTP): when SMTP is not configured,
# return the password-reset link in the API response so the flow can be
# demonstrated without a mail server. Always clearly labelled; never active
# when SMTP_HOST is set.
DEV_SHOW_RESET_LINK = os.getenv(
    "DEV_SHOW_RESET_LINK", "true").strip().lower() in {"1", "true", "yes", "on"}

# SMTP settings for password-reset emails. Empty SMTP_HOST disables sending.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
