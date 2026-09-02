"""Financial Behavior Assessment endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_applicant, get_owned_application
from ..db import get_db
from ..models import Applicant
from ..questionnaire import questions_public, save_questionnaire
from ..schemas import QuestionnaireSubmit, QuestionnaireSubmitResponse

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.get("/questions")
def get_questions():
    # static question set for the UI — no session required
    return questions_public()


@router.post("/psychometric", response_model=QuestionnaireSubmitResponse)
def submit_questionnaire(
    payload: QuestionnaireSubmit,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(payload.application_id, applicant, db)
    return save_questionnaire(db, application, payload.answers)
