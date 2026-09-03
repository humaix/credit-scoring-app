"""Employment / financial document verification endpoints (Phase 3)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_applicant, get_owned_application
from ..db import get_db
from ..employment_docs import submit_employment
from ..models import Applicant
from ..schemas import EmploymentSubmitRequest, EmploymentSubmitResponse

router = APIRouter(prefix="/api/employment", tags=["employment"])


@router.post("", response_model=EmploymentSubmitResponse)
def submit(
    payload: EmploymentSubmitRequest,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return submit_employment(db, application, payload)
