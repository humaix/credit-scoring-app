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
