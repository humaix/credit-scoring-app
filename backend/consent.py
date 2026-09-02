"""Data-consent capture for alternative data sources.

The scoring pipeline never silently claims access to external data: each
category is explicitly consented to, stored with the application, and the
mock provider fetches (phase 4) are gated on it.
"""

from sqlalchemy.orm import Session

from .errors import ApiError
from .flow import STEP_ORDER
from .models import Application, ConsentRecord

CONSENT_CATEGORIES = (
    "wallet_activity", "telecom_activity",
    "digital_transactions", "previous_loan_info",
)

CONSENT_DESCRIPTIONS = {
    "wallet_activity": (
        "Mobile wallet activity summary from your wallet provider "
        "(simulated for this prototype)"),
    "telecom_activity": (
        "Telecom usage summary from your mobile operator "
        "(simulated for this prototype)"),
    "digital_transactions": "Digital purchase frequency information",
    "previous_loan_info": "Previous loan and repayment history",
}

CONSENT_NOTICE = (
    "Assessment requires consent to all four data categories. If consent is "
    "declined, that data cannot be used and no score can be produced for "
    "this application."
)


def grant_consent(db: Session, application: Application, choices: dict) -> dict:
    """Record consent for the four categories and advance the application."""
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

    declined = [c for c in CONSENT_CATEGORIES if not choices.get(c)]
    if declined:
        raise ApiError(
            422, "consent_required",
            f"Assessment requires consent to all data categories; declined: "
            f"{', '.join(declined)}. {CONSENT_NOTICE}")

    record = ConsentRecord(
        application_id=application.id,
        wallet_activity=True,
        telecom_activity=True,
        digital_transactions=True,
        previous_loan_info=True,
    )
    db.add(record)
    application.status = "consented"
    db.commit()
    return {
        "status": "consented",
        "categories": list(CONSENT_CATEGORIES),
        "granted_at": record.granted_at,
        "notice": CONSENT_NOTICE,
    }
