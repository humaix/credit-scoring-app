"""Scoring endpoint — connects the flow to the existing ML pipeline."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_applicant, get_owned_application
from ..db import get_db
from ..models import Applicant
from ..schemas import ApplicationRef, ScoringResponse
from ..scoring import run_scoring

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.post("/predict", response_model=ScoringResponse)
def predict(
    payload: ApplicationRef,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return run_scoring(db, application)
