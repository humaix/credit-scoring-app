"""Data-consent capture for alternative data sources.

The scoring pipeline never silently claims access to external data: each
category is explicitly consented to, stored with the application, and the
mock provider fetches (phase 4) are gated on it.

Phase 2 makes the category set conditional: applicants who declared a bank
account are also asked for bank account / bank statement data consent, and
that category is never shown as required to applicants without one —
financial inclusion means no bank account never blocks assessment.
"""

from sqlalchemy.orm import Session

from .errors import ApiError
from .flow import STEP_ORDER
from .models import Application, ConsentRecord, EmploymentVerification

CONSENT_CATEGORIES = (
    "wallet_activity", "telecom_activity",
    "digital_transactions", "previous_loan_info",
    # credit-information verification consent (spec section 4) — required
    # before the credit verification step can run
    "credit_information_verification",
)

# only applicable (and only required) for applications with a bank account
BANK_CATEGORY = "bank_account_data"

CONSENT_DESCRIPTIONS = {
    "wallet_activity": (
        "Mobile wallet activity summary from your wallet provider "
        "(simulated for this prototype)"),
    "telecom_activity": (
        "Telecom usage summary from your mobile operator "
        "(simulated for this prototype)"),
    "digital_transactions": "Digital purchase frequency information",
    "previous_loan_info": "Previous loan and repayment history",
    "credit_information_verification": (
        "I authorize the application/service, where legally permitted and "
        "applicable, to obtain and verify my credit information from the "
        "State Bank of Pakistan's Electronic Credit Information Bureau "
        "(eCIB) and/or an SBP-licensed credit bureau for the purpose of "
        "assessing my loan application. (This prototype is not connected to "
        "eCIB or any credit bureau — verification runs as a clearly labelled "
        "demo simulation.)"),
    "bank_account_data": (
        "Bank account and bank statement data (document-based prototype "
        "verification — no bank or open-banking integration in this prototype)"),
}

# generic wording: the concrete category count depends on the application
CONSENT_NOTICE = (
    "Assessment requires consent to all applicable data categories. If "
    "consent is declined, that data cannot be used and no score can be "
    "produced for this application."
)


def applicable_categories(has_bank_account: bool) -> tuple:
    """The categories an application must consent to, given its declaration."""
    if has_bank_account:
        return CONSENT_CATEGORIES + (BANK_CATEGORY,)
    return CONSENT_CATEGORIES


def consent_notice(has_bank_account: bool) -> str:
    count = "six" if has_bank_account else "five"
    return (
        f"Assessment requires consent to all {count} applicable data "
        "categories. If consent is declined, that data cannot be used and no "
        "score can be produced for this application."
    )


def grant_consent(db: Session, application: Application, choices: dict) -> dict:
    """Record consent for the applicable categories and advance the application."""
    existing = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.application_id == application.id)
        .first()
    )
    if existing is not None:
        raise ApiError(409, "consent_already_recorded",
                       "Consent has already been recorded for this application")

    if application.status != "verified":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: {STEP_ORDER}")

    # Phase 3: the employment / document step happens while the application
    # is 'verified' and must be completed before consent can be granted
    employment = (
        db.query(EmploymentVerification)
        .filter(EmploymentVerification.application_id == application.id)
        .first()
    )
    if employment is None:
        raise ApiError(
            409, "employment_verification_required",
            "Complete the employment & financial document step before "
            "granting consent for this application")

    required = applicable_categories(application.has_bank_account)
    declined = [c for c in required if not choices.get(c)]
    if declined:
        raise ApiError(
            422, "consent_required",
            f"Assessment requires consent to all applicable data categories; "
            f"declined: {', '.join(declined)}. {CONSENT_NOTICE}")

    record = ConsentRecord(
        application_id=application.id,
        wallet_activity=True,
        telecom_activity=True,
        digital_transactions=True,
        previous_loan_info=True,
        credit_information_verification=True,
        # bank data consent exists only for bank-account holders; for the
        # alternative-data path the category is not applicable at all
        bank_account_data=bool(application.has_bank_account),
    )
    db.add(record)
    application.status = "consented"
    db.commit()
    return {
        "status": "consented",
        "categories": list(required),
        "granted_at": record.granted_at,
        "notice": consent_notice(application.has_bank_account),
    }
