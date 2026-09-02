"""Simulated identity verification (clearly labelled mock).

The VerificationProvider interface mirrors a real OTP/KYC flow so a genuine
NADRA / telecom integration can replace MockVerificationProvider later
without changing the business logic. No real external service is contacted,
and identifiers (CNIC, mobile) never reach the ML model.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import config
from .errors import ApiError
from .models import Application, VerificationRecord

OTP_NOTICE = (
    "Simulated OTP - no real SMS is sent. This prototype has no NADRA, "
    "Easypaisa, JazzCash or telecom integration."
)

_STEP_ORDER = "created -> verified -> consented -> assessed -> scored"


class VerificationProvider:
    """Adapter interface for a real OTP / identity provider."""

    def send_otp(self, mobile: str) -> str:
        raise NotImplementedError

    def check_identity(self, cnic: str, mobile: str) -> bool:
        raise NotImplementedError


class MockVerificationProvider(VerificationProvider):
    """Deterministic simulation used by the prototype."""

    def send_otp(self, mobile: str) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def check_identity(self, cnic: str, mobile: str) -> bool:
        # simulated registry miss: CNICs starting with 00000 never match,
        # so the 'Failed' status path can be demonstrated in tests/demo
        return not cnic.startswith("00000")


_provider: VerificationProvider = MockVerificationProvider()


def set_provider(provider: VerificationProvider) -> None:
    """Swap in a real provider implementation (future integration point)."""
    global _provider
    _provider = provider


def _otp_hash(application_id: int, code: str) -> str:
    return hashlib.sha256(f"{application_id}:{code}".encode()).hexdigest()


def _record(db: Session, application: Application) -> VerificationRecord:
    record = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.application_id == application.id)
        .first()
    )
    if record is None:
        record = VerificationRecord(application_id=application.id)
        db.add(record)
    return record


def request_otp(db: Session, application: Application) -> dict:
    """Generate and 'send' a simulated OTP for the application's applicant."""
    if application.status != "created":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: {_STEP_ORDER}")

    record = _record(db, application)
    if record.status == "verified":
        raise ApiError(409, "already_verified",
                       "Identity is already verified for this application")

    code = _provider.send_otp(application.applicant.mobile)
    record.status = "pending"
    record.otp_hash = _otp_hash(application.id, code)
    record.otp_expires_at = datetime.utcnow() + timedelta(
        seconds=config.OTP_TTL_SECONDS)
    record.otp_attempts = 0
    db.commit()

    result = {
        "status": "pending",
        "expires_in_seconds": config.OTP_TTL_SECONDS,
        "notice": OTP_NOTICE,
    }
    if config.DEV_RETURN_OTP:
        result["simulated_otp"] = code
    return result


def verify_otp(db: Session, application: Application, code: str) -> dict:
    """Check the submitted OTP and run the simulated identity lookup."""
    if application.status != "created":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: {_STEP_ORDER}")

    record = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.application_id == application.id)
        .first()
    )
    if record is None or record.status != "pending" or not record.otp_hash:
        raise ApiError(409, "no_pending_otp", "Request an OTP first")

    expired = (
        record.otp_expires_at is None
        or record.otp_expires_at < datetime.utcnow()
    )
    if expired or record.otp_attempts >= config.OTP_MAX_ATTEMPTS:
        record.status = "failed"
        db.commit()
        raise ApiError(409, "otp_expired_or_locked",
                       "OTP expired or too many attempts - request a new OTP")

    if _otp_hash(application.id, code.strip()) != record.otp_hash:
        record.otp_attempts += 1
        remaining = config.OTP_MAX_ATTEMPTS - record.otp_attempts
        if remaining <= 0:
            record.status = "failed"
            db.commit()
            return {"status": "failed",
                    "message": "Too many incorrect attempts - request a new OTP"}
        db.commit()
        return {"status": "pending", "attempts_remaining": remaining,
                "message": "Incorrect OTP"}

    # correct code -> simulated registry identity check
    applicant = application.applicant
    if not _provider.check_identity(applicant.cnic, applicant.mobile):
        record.status = "failed"
        db.commit()
        return {
            "status": "failed",
            "message": "Simulated identity check found no matching record "
                       "(prototype behaviour)",
            "notice": OTP_NOTICE,
        }

    record.status = "verified"
    record.verified_at = datetime.utcnow()
    record.otp_hash = None  # one-time use
    application.status = "verified"
    db.commit()
    return {"status": "verified", "verified_at": record.verified_at,
            "notice": OTP_NOTICE}
