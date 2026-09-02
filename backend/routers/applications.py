"""Loan application endpoints — create, list, detail, PDF report."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import applicant_public, get_current_applicant, get_owned_application
from ..db import get_db
from ..errors import ApiError
from ..models import Applicant, Application
from ..scoring import latest_report_path
from ..schemas import (
    ApplicationCreated, ApplicationCreate, ApplicationDetail, ApplicationSummary,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _summary(application: Application) -> dict:
    return {
        "id": application.id,
        "status": application.status,
        "occupation": application.occupation,
        "requested_loan_size": application.requested_loan_size,
        "repayment_score": (
            application.assessment.repayment_score if application.assessment else None
        ),
        "score_category": (
            application.assessment.score_category if application.assessment else None
        ),
        "created_at": application.created_at,
    }


def _detail(application: Application) -> dict:
    data = {
        **_summary(application),
        "age": application.age,
        "monthly_income": application.monthly_income,
        "monthly_debt_payments": application.monthly_debt_payments,
        "existing_loan_history": application.existing_loan_history,
        "digital_purchase_frequency": application.digital_purchase_frequency,
        "applicant": applicant_public(application.applicant),
        "verification": None,
        "consent": None,
        "questionnaire": None,
        "assessment": None,
    }
    if application.verification is not None:
        data["verification"] = {
            "status": application.verification.status,
            "provider": application.verification.provider,
            "verified_at": application.verification.verified_at,
        }
    if application.consent is not None:
        data["consent"] = {
            "wallet_activity": application.consent.wallet_activity,
            "telecom_activity": application.consent.telecom_activity,
            "digital_transactions": application.consent.digital_transactions,
            "previous_loan_info": application.consent.previous_loan_info,
            "granted_at": application.consent.granted_at,
        }
    if application.questionnaire is not None:
        data["questionnaire"] = {
            "psychometric_score": application.questionnaire.psychometric_score,
            "consistency_warnings": application.questionnaire.consistency_warnings,
            "completed_at": application.questionnaire.completed_at,
        }
    if application.assessment is not None:
        # full persisted assessment — powers the results dashboard with the
        # exact values the scoring run produced (and the PDF shows)
        data["assessment"] = {
            "repayment_score": application.assessment.repayment_score,
            "raw_score": application.assessment.raw_score,
            "score_category": application.assessment.score_category,
            "base_value": application.assessment.base_value,
            "positive_contributors": application.assessment.positive_contributors,
            "negative_contributors": application.assessment.negative_contributors,
            "all_contributions": application.assessment.all_contributions,
            "explanation": application.assessment.explanation,
            "explanation_source": application.assessment.explanation_source,
            "created_at": application.assessment.created_at,
        }
    return data


@router.post("", response_model=ApplicationCreated, status_code=201)
def create_application(
    payload: ApplicationCreate,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = Application(
        applicant_id=applicant.id,
        age=payload.age,
        occupation=payload.occupation,
        monthly_income=payload.monthly_income,
        monthly_debt_payments=payload.monthly_debt_payments,
        existing_loan_history=payload.existing_loan_history,
        requested_loan_size=payload.requested_loan_size,
        digital_purchase_frequency=payload.digital_purchase_frequency,
        status="created",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return ApplicationCreated(
        application_id=application.id, status=application.status)


@router.get("", response_model=list[ApplicationSummary])
def list_applications(
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Application)
        .filter(Application.applicant_id == applicant.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [_summary(a) for a in rows]


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: int,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(application_id, applicant, db)
    return _detail(application)


@router.get("/{application_id}/report")
def get_application_report(
    application_id: int,
    applicant: Applicant = Depends(get_current_applicant),
    db: Session = Depends(get_db),
):
    application = get_owned_application(application_id, applicant, db)
    if application.assessment is None:
        raise ApiError(
            409, "not_scored",
            "Score the application before requesting the assessment report")
    path = latest_report_path(db, application)
    return FileResponse(
        path, media_type="application/pdf", filename=path.name)
