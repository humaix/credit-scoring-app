"""Simulated identity-verification endpoints (OTP flow)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import verification
from ..auth import get_current_applicant, get_owned_application
from ..db import get_db
from ..models import Applicant
from ..schemas import (
    ApplicationRef, OtpRequestResponse, OtpVerifyRequest, OtpVerifyResponse,
)

router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.post("/request-otp", response_model=OtpRequestResponse)
def request_otp(
    payload: ApplicationRef,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return verification.request_otp(db, application)


@router.post("/verify-otp", response_model=OtpVerifyResponse)
def verify_otp(
    payload: OtpVerifyRequest,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return verification.verify_otp(db, application, payload.code)
