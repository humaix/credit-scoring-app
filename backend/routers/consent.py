"""Data-consent endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_applicant, get_owned_application
from ..consent import CONSENT_DESCRIPTIONS, CONSENT_NOTICE, grant_consent
from ..db import get_db
from ..models import Applicant
from ..schemas import ConsentGrantRequest, ConsentGrantResponse

router = APIRouter(prefix="/api/consent", tags=["consent"])


@router.get("/info")
def consent_info():
    # category descriptions for the consent screen — no session required
    return {"categories": CONSENT_DESCRIPTIONS, "notice": CONSENT_NOTICE}


@router.post("", response_model=ConsentGrantResponse)
def grant(
    payload: ConsentGrantRequest,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return grant_consent(db, application, payload.model_dump())
