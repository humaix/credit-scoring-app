"""Credit-information verification endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_applicant, get_owned_application
from ..credit_verification import (
    CREDIT_CONSENT_TEXT, DEMO_NOTICE, verify_credit_history,
)
from ..db import get_db
from ..models import Applicant
from ..schemas import ApplicationRef, CreditVerificationPublic

router = APIRouter(prefix="/api/credit-verification", tags=["credit-verification"])


@router.get("/info")
def credit_verification_info():
    # wording for the consent/verification screens — no session required
    return {
        "consent_text": CREDIT_CONSENT_TEXT,
        "demo_notice": DEMO_NOTICE,
    }


@router.post("", response_model=CreditVerificationPublic)
def verify(
    payload: ApplicationRef,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return verify_credit_history(db, application)
