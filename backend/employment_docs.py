"""Employment / financial document verification (Phase 3).

Salaried applicants declare their employer and monthly salary and capture a
salary slip; business owners and self-employed applicants declare their
business and income and capture a bank statement when they declared a bank
account. Documents run the same quality checks as CNIC images (format,
dimensions, size, brightness) plus a duplicate screen against the
applicant's stored CNIC images — catching lazy reuse of an unrelated photo.

This prototype performs NO OCR and has no employer / bank / open-banking
integration: reading a document would not prove it authentic anyway. A
successfully captured document is therefore honestly labelled
"Pending Provider Verification" (status: needs_review) and every captured
document carries the same notice. The statuses data_matched and
could_not_verify stay in the vocabulary for a future authorized provider
but are never produced here.
"""

import hashlib
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from . import config
from .cnic_images import parse_image_data
from .errors import ApiError
from .flow import STEP_ORDER
from .models import Applicant, Application, EmploymentVerification

SALARIED_OCCUPATION = "Salaried"
BUSINESS_OCCUPATIONS = ("Business Owner", "Self-Employed")

# status -> the label shown to applicants
DOC_STATUS_LABELS = {
    "needs_review": "Pending Provider Verification",
    "not_required": "Not Required",
    # reserved for a future authorized employer/bank provider — without OCR
    # there is nothing to match against, so this prototype never sets them
    "data_matched": "Data Matched",
    "could_not_verify": "Could Not Verify",
}

DOC_STATUS_NOTICE = (
    "Document-Based Prototype Verification: the document was captured and "
    "passed quality checks. This prototype performs no OCR and no employer "
    "or bank verification — the document is pending provider verification "
    "in any real deployment."
)

# declared salary/income vs the application's declared monthly income within
# this fraction counts as consistent (bonuses, deductions and rounding make
# small gaps normal)
SALARY_INCOME_TOLERANCE = 0.2

_DOC_LABELS = {
    "salary_slip": "Salary slip",
    "bank_statement": "Bank statement",
}


def requirements_for(occupation: str, has_bank_account: bool) -> tuple:
    """The document an occupation must capture: (doc_type, human label).

    doc_type is "salary_slip", "bank_statement" or "not_required" (no
    document applies — business applicants without a bank account and every
    other occupation proceed on alternative data).
    """
    if occupation == SALARIED_OCCUPATION:
        return "salary_slip", _DOC_LABELS["salary_slip"]
    if occupation in BUSINESS_OCCUPATIONS and has_bank_account:
        return "bank_statement", _DOC_LABELS["bank_statement"]
    return "not_required", "No document"


def no_document_notice(occupation: str, has_bank_account: bool) -> str:
    """Why no document is captured, in applicant-facing words."""
    if occupation in BUSINESS_OCCUPATIONS and not has_bank_account:
        return (
            "No bank statement is required because this application did "
            "not declare a bank account — the assessment proceeds on "
            "alternative data."
        )
    return (
        "No employment document is applicable for this occupation — the "
        "assessment proceeds on alternative data."
    )


def parse_document(doc_type: str, data: str) -> tuple:
    """Validate one document image; return (raw bytes, extension, info)."""
    label = _DOC_LABELS.get(doc_type, "Employment document")
    return parse_image_data(label, "employment_document", data)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def duplicate_of_cnic(applicant: Applicant, raw: bytes) -> str | None:
    """Describe a byte-identical match against the applicant's CNIC images."""
    document_hash = _sha256(raw)
    directory = config.UPLOADS_DIR / "cnic" / f"applicant_{applicant.id}"
    for side, filename in (("front", applicant.cnic_front_filename),
                           ("back", applicant.cnic_back_filename)):
        if not filename:
            continue
        path = directory / filename
        if path.exists() and _sha256(path.read_bytes()) == document_hash:
            return f"identical to the uploaded CNIC {side} image"
    return None


def build_checks(doc_type: str, info: dict | None,
                 declared_income: float | None = None,
                 monthly_income: float | None = None,
                 no_doc_detail: str | None = None) -> list:
    """The prototype checks performed on one submission, as stored records."""
    if doc_type == "not_required" or info is None:
        checks = [{
            "check": "document_applicability",
            "result": "pass",
            "detail": no_doc_detail
                      or "no employment document applicable for this application",
        }]
    else:
        checks = [
            {
                "check": "document_readable",
                "result": "pass",
                "detail": (f"{info['format']} {info['width']}x{info['height']}, "
                           f"mean brightness {info['brightness']}"),
            },
            {
                "check": "duplicate_screen",
                "result": "pass",
                "detail": "not byte-identical to previously uploaded documents",
            },
        ]
    if declared_income is not None and monthly_income:
        gap = abs(declared_income - monthly_income) / monthly_income
        if gap > SALARY_INCOME_TOLERANCE:
            checks.append({
                "check": "income_consistency",
                "result": "flag",
                "detail": (f"declared salary/income {declared_income:,.0f} "
                           f"differs from the application's monthly income "
                           f"{monthly_income:,.0f} by {gap:.0%} — flagged "
                           f"for review"),
            })
        else:
            checks.append({
                "check": "income_consistency",
                "result": "pass",
                "detail": (f"declared salary/income {declared_income:,.0f} is "
                           f"within {SALARY_INCOME_TOLERANCE:.0%} of the "
                           f"application's monthly income "
                           f"{monthly_income:,.0f}"),
            })
    return checks


def store_document(applicant_id: int, doc_type: str,
                   raw: bytes, extension: str) -> str:
    """Write the validated document under the applicant's upload directory."""
    directory = config.UPLOADS_DIR / "employment" / f"applicant_{applicant_id}"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{doc_type}_{stamp}_{secrets.token_hex(4)}.{extension}"
    (directory / filename).write_bytes(raw)
    return filename


def _check_fields(payload, allowed: set, required: set, message: str) -> None:
    """Reject fields the occupation's branch never uses; find missing ones."""
    values = {
        "employer_name": payload.employer_name,
        "business_name": payload.business_name,
        "declared_income": payload.declared_income,
        "document_image": payload.document_image,
    }
    unexpected = sorted(name for name, value in values.items()
                        if value is not None and name not in allowed)
    if unexpected:
        raise ApiError(
            422, "employment_details_not_applicable",
            f"Not applicable for this occupation: {', '.join(unexpected)}")
    missing = sorted(name for name in required if not values[name])
    if missing:
        raise ApiError(422, "employment_details_required", message.format(
            missing=", ".join(missing)))


def submit_employment(db: Session, application: Application, payload) -> dict:
    """Validate and store the Phase 3 employment / document submission."""
    existing = (
        db.query(EmploymentVerification)
        .filter(EmploymentVerification.application_id == application.id)
        .first()
    )
    if existing is not None:
        raise ApiError(
            409, "employment_already_submitted",
            "Employment details have already been submitted for this "
            "application")

    if application.status != "verified":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: "
            f"{STEP_ORDER}")

    doc_type, _ = requirements_for(
        application.occupation, application.has_bank_account)

    if doc_type == "salary_slip":
        _check_fields(
            payload,
            allowed={"employer_name", "declared_income", "document_image"},
            required={"employer_name", "declared_income", "document_image"},
            message=("Salaried applicants must provide: {missing}"))
    elif doc_type == "bank_statement":
        _check_fields(
            payload,
            allowed={"business_name", "declared_income", "document_image"},
            required={"business_name", "declared_income", "document_image"},
            message=("Business owners / self-employed applicants with a "
                     "bank account must provide: {missing}"))
    elif application.occupation in BUSINESS_OCCUPATIONS:
        # business branch without a bank account: declare, no statement
        _check_fields(
            payload,
            allowed={"business_name", "declared_income"},
            required={"business_name", "declared_income"},
            message=("Business owners / self-employed applicants must "
                     "provide: {missing}"))
    else:
        _check_fields(payload, allowed=set(), required=set(), message="")

    if doc_type == "not_required":
        notice = no_document_notice(
            application.occupation, application.has_bank_account)
        record = EmploymentVerification(
            application_id=application.id,
            occupation=application.occupation,
            doc_type="not_required",
            employer_name=payload.employer_name,
            business_name=payload.business_name,
            declared_income=payload.declared_income,
            status="not_required",
            checks=build_checks("not_required", None,
                                declared_income=payload.declared_income,
                                monthly_income=application.monthly_income,
                                no_doc_detail=notice),
        )
        db.add(record)
        db.commit()
        return {
            "status": record.status,
            "status_label": DOC_STATUS_LABELS[record.status],
            "doc_type": record.doc_type,
            "checks": record.checks,
            "notice": notice,
        }

    # a document is required — validate, screen and store it
    raw, extension, info = parse_document(doc_type, payload.document_image)
    duplicate = duplicate_of_cnic(application.applicant, raw)
    if duplicate:
        raise ApiError(
            422, "employment_document",
            f"{_DOC_LABELS[doc_type]} image: {duplicate} — capture the "
            f"actual document")
    filename = store_document(
        application.applicant_id, doc_type, raw, extension)

    record = EmploymentVerification(
        application_id=application.id,
        occupation=application.occupation,
        doc_type=doc_type,
        employer_name=payload.employer_name,
        business_name=payload.business_name,
        declared_income=payload.declared_income,
        filename=filename,
        status="needs_review",
        checks=build_checks(doc_type, info,
                            declared_income=payload.declared_income,
                            monthly_income=application.monthly_income),
    )
    db.add(record)
    db.commit()
    return {
        "status": record.status,
        "status_label": DOC_STATUS_LABELS[record.status],
        "doc_type": record.doc_type,
        "checks": record.checks,
        "notice": DOC_STATUS_NOTICE,
    }
