"""Registration, login, logout and password-reset endpoints (Phase 1)."""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, mailer, security
from ..auth import (
    applicant_public, get_current_applicant, new_session_token,
)
from ..cnic_images import CNIC_STATUS_NOTICE, parse_image, store_image
from ..db import get_db
from ..errors import ApiError
from ..models import Applicant, PasswordResetToken
from ..schemas import (
    ForgotPasswordRequest, ForgotPasswordResponse, LoginRequest,
    LoginResponse, LogoutResponse, RegisterRequest, RegisterResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# identical wording for every failed login so the response cannot be used to
# probe which CNICs have accounts
_LOGIN_FAILED = ApiError(
    401, "invalid_credentials", "CNIC or password is incorrect")

# identical response for every forgot-password request, whether or not the
# CNIC has an account — no account enumeration
_RESET_SENT_MESSAGE = (
    "If an account exists for this CNIC, a password reset link has been "
    "sent to the registered email address.")


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Applicant).filter(Applicant.cnic == payload.cnic).first()
    if existing is not None:
        raise ApiError(
            409, "already_registered",
            "An applicant with this CNIC is already registered - log in instead")

    email = payload.email  # already stripped/lowercased by the schema
    existing_email = (
        db.query(Applicant).filter(Applicant.email == email).first())
    if existing_email is not None:
        raise ApiError(
            409, "email_already_registered",
            "An account with this email address already exists")

    # validate both images before anything is persisted
    front_raw, front_ext = parse_image("front", payload.cnic_front_image)
    back_raw, back_ext = parse_image("back", payload.cnic_back_image)

    applicant = Applicant(
        full_name=payload.full_name.strip(),
        cnic=payload.cnic,
        mobile=payload.mobile,
        email=email,
        password_hash=security.hash_password(payload.password),
        session_token=new_session_token(),
        cnic_status="prototype_verified",
    )
    db.add(applicant)
    stored: list[Path] = []
    try:
        db.flush()  # applicant.id is needed for the upload directory
        applicant.cnic_front_filename = store_image(
            applicant.id, "front", front_raw, front_ext)
        applicant.cnic_back_filename = store_image(
            applicant.id, "back", back_raw, back_ext)
        stored = [
            config.UPLOADS_DIR / "cnic" / f"applicant_{applicant.id}"
            / applicant.cnic_front_filename,
            config.UPLOADS_DIR / "cnic" / f"applicant_{applicant.id}"
            / applicant.cnic_back_filename,
        ]
        db.commit()
    except IntegrityError:
        # a concurrent registration with the same CNIC or email lost the race
        db.rollback()
        for path in stored:
            path.unlink(missing_ok=True)  # never leave orphaned uploads
        raise ApiError(
            409, "already_registered",
            "An applicant with this CNIC or email is already registered - "
            "log in instead")
    db.refresh(applicant)
    return RegisterResponse(
        session_token=applicant.session_token,  # type: ignore[arg-type]
        applicant=applicant_public(applicant),  # type: ignore[arg-type]
        cnic_notice=CNIC_STATUS_NOTICE,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    applicant = db.query(Applicant).filter(Applicant.cnic == payload.cnic).first()
    if applicant is None:
        # burn the same CPU time as a real password check, then fail
        # identically — timing must not reveal whether the CNIC exists
        security.dummy_verify(payload.password)
        raise _LOGIN_FAILED
    if not applicant.password_hash or not security.verify_password(
            payload.password, applicant.password_hash):
        raise _LOGIN_FAILED

    if not applicant.session_token:
        # previous session was logged out (token nulled) — issue a fresh one
        applicant.session_token = new_session_token()
        db.commit()

    applications = sorted(applicant.applications, key=lambda a: a.created_at,
                          reverse=True)
    return LoginResponse(
        session_token=applicant.session_token,  # type: ignore[arg-type]
        applicant=applicant_public(applicant),  # type: ignore[arg-type]
        applications=[
            {
                "id": a.id,
                "status": a.status,
                "occupation": a.occupation,
                "requested_loan_size": a.requested_loan_size,
                "repayment_score": a.assessment.repayment_score if a.assessment else None,
                "score_category": a.assessment.score_category if a.assessment else None,
                "created_at": a.created_at,
            }
            for a in applications
        ],
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    applicant.session_token = None
    db.commit()
    return LogoutResponse(status="logged_out")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest,
                    db: Session = Depends(get_db)):
    response = ForgotPasswordResponse(message=_RESET_SENT_MESSAGE)
    applicant = (
        db.query(Applicant).filter(Applicant.cnic == payload.cnic).first())
    if applicant is None or not applicant.email:
        return response  # same response as the success path — no enumeration

    # one outstanding reset token per applicant: invalidate older ones
    db.query(PasswordResetToken).filter(
        PasswordResetToken.applicant_id == applicant.id).delete()

    raw_token, token_hash = security.new_reset_token()
    db.add(PasswordResetToken(
        applicant_id=applicant.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow()
        + timedelta(minutes=config.RESET_TOKEN_TTL_MINUTES),
    ))
    db.commit()

    reset_url = f"{config.APP_BASE_URL}/reset-password?token={raw_token}"
    if mailer.smtp_configured():
        mailer.send_reset_email(applicant.email, reset_url)
    elif config.DEV_SHOW_RESET_LINK:
        # development/demo mode (mirrors the simulated-OTP switch): the link
        # is returned here because no mail server is configured. Clearly
        # labelled, and never active once SMTP is configured.
        response.dev_reset_url = reset_url
        response.dev_notice = (
            "Development mode: SMTP is not configured, so the reset link is "
            "shown here instead of being emailed. This never happens when "
            "SMTP is configured.")
    return response


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(payload: ResetPasswordRequest,
                   db: Session = Depends(get_db)):
    token_hash = security.hash_reset_token(payload.token)
    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first())
    if (record is None or record.used_at is not None
            or record.expires_at < datetime.utcnow()):
        # unknown, already-used and expired tokens are indistinguishable
        raise ApiError(
            400, "invalid_or_expired",
            "This password reset link is invalid or has expired - "
            "request a new one")

    record.applicant.password_hash = security.hash_password(
        payload.new_password)
    record.used_at = datetime.utcnow()  # single use
    db.commit()
    return ResetPasswordResponse(
        message="Password updated. Log in with your new password.")
