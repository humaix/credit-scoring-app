"""Loan application endpoints — create, list, detail, PDF report."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import (
    applicant_public, get_current_applicant, get_owned_application, mask_iban,
)
from ..credit_verification import credit_verification_public
from ..db import get_db
from ..employment_docs import (
    DOC_STATUS_LABELS, DOC_STATUS_NOTICE, no_document_notice,
)
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
        # loan history comes from the credit verification step — null until
        # that step has run (applicants never declare it themselves)
        "existing_loan_history": application.existing_loan_history,
        "digital_purchase_frequency": application.digital_purchase_frequency,
        # bank declaration — the raw IBAN/account number never leaves the API
        "has_bank_account": application.has_bank_account,
        "bank_name": application.bank_name,
        "bank_account_title": application.bank_account_title,
        "bank_iban_masked": mask_iban(application.bank_iban) or None,
        "wallet_provider": application.wallet_provider,
        "applicant": applicant_public(application.applicant),
        "verification": None,
        "employment": None,
        "credit_verification": None,
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
    if application.employment is not None:
        # Phase 3: prototype document verification — the stored filename
        # never leaves the API, only the fact that a document was captured
        record = application.employment
        data["employment"] = {
            "occupation": record.occupation,
            "doc_type": record.doc_type,
            "employer_name": record.employer_name,
            "business_name": record.business_name,
            "declared_income": record.declared_income,
            "status": record.status,
            "status_label": DOC_STATUS_LABELS.get(record.status, record.status),
            "document_captured": record.filename is not None,
            "checks": record.checks,
            "notice": (
                DOC_STATUS_NOTICE if record.filename is not None
                else no_document_notice(
                    record.occupation, application.has_bank_account)),
            "created_at": record.created_at,
        }
    if application.consent is not None:
        data["consent"] = {
            "wallet_activity": application.consent.wallet_activity,
            "telecom_activity": application.consent.telecom_activity,
            "digital_transactions": application.consent.digital_transactions,
            "previous_loan_info": application.consent.previous_loan_info,
            "credit_information_verification": (
                application.consent.credit_information_verification),
            "bank_account_data": application.consent.bank_account_data,
            "granted_at": application.consent.granted_at,
        }
    if application.credit_verification is not None:
        data["credit_verification"] = credit_verification_public(
            application.credit_verification)
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
            "interpretation": application.assessment.interpretation,
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
        # existing_loan_history stays null here — the credit verification
        # step fills it in after consent
        requested_loan_size=payload.requested_loan_size,
        digital_purchase_frequency=payload.digital_purchase_frequency,
        # Phase 2: the bank-account answer steers the rest of the flow
        # (bank details exist only for account holders; consent adapts)
        has_bank_account=payload.has_bank_account,
        bank_name=payload.bank_name,
        bank_account_title=payload.bank_account_title,
        bank_iban=payload.bank_iban,
        wallet_provider=payload.wallet_provider,
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
