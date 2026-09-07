"""Credit-information verification step (spec sections 4-8).

Applicants no longer type their loan history into the form: the category is
obtained through a credit-information verification step that runs after
consent (a sub-step while the application is 'consented', mirroring how the
employment step works while 'verified').

The PROTOTYPE provider is MockCreditVerificationService — a clearly labelled
simulation. No eCIB or SBP-licensed bureau is contacted; swapping in a real
authorized provider later means implementing the same fetch interface and
changing the module-level service instance.

derive_loan_history() is a documented, deterministic Python function — the
LLM never decides the loan-history category.
"""

import random

from sqlalchemy.orm import Session

from .errors import ApiError
from .flow import STEP_ORDER
from .models import Application, ConsentRecord, CreditVerification

# spec section 4 wording (the demo-simulation caveat is appended in the UI)
CREDIT_CONSENT_TEXT = (
    "I authorize the application/service, where legally permitted and "
    "applicable, to obtain and verify my credit information from the State "
    "Bank of Pakistan's Electronic Credit Information Bureau (eCIB) and/or "
    "an SBP-licensed credit bureau for the purpose of assessing my loan "
    "application."
)

DEMO_NOTICE = (
    "Demo Credit Verification — credit-history information shown here is "
    "simulated for demonstration purposes and is not retrieved from a real "
    "credit bureau."
)

# at least this many installments paid on time counts as "consistently on
# time" (spec examples: 18 -> Good, 8 -> Delayed)
GOOD_ON_TIME_THRESHOLD = 12


def derive_loan_history(credit_data: dict) -> tuple:
    """Deterministically map the six credit fields to a model category.

    Returns (existing_loan_history, inconsistent). Documented rules, applied
    in order:
      1. no previous loan and no outstanding debt -> No Previous Loan
      2. overdue/default recorded                  -> Previous Default
      3. borrowing + consistently on time          -> Good Repayment History
      4. borrowing with delays but no default      -> Delayed Repayment History

    Contradictory records (e.g. no previous loan but outstanding debt > 0)
    are flagged inconsistent instead of being silently mapped — the flag is
    stored and shown, so the category can never mislead on its own.
    """
    has_loan = bool(credit_data["has_previous_loan"])
    has_card = bool(credit_data["has_credit_card"])
    outstanding = float(credit_data["total_outstanding_amount"])
    on_time = int(credit_data["installments_paid_on_time"])
    defaulted = bool(credit_data["has_overdue_or_default"])
    debt = float(credit_data["total_existing_debt"])

    # a record with no credit line at all cannot carry debt or repayments
    inconsistent = (not has_loan and not has_card
                    and (outstanding > 0 or debt > 0 or on_time > 0))

    borrowing = has_loan or has_card or outstanding > 0 or debt > 0
    if not borrowing and not defaulted:
        return "No Previous Loan", inconsistent
    if defaulted:
        return "Previous Default", inconsistent
    if on_time >= GOOD_ON_TIME_THRESHOLD:
        return "Good Repayment History", inconsistent
    return "Delayed Repayment History", inconsistent


def _credit_data(has_loan, has_card, outstanding, on_time, defaulted, debt):
    return {
        "has_previous_loan": has_loan,
        "has_credit_card": has_card,
        "total_outstanding_amount": outstanding,
        "installments_paid_on_time": on_time,
        "has_overdue_or_default": defaulted,
        "total_existing_debt": debt,
    }


class MockCreditVerificationService:
    """Demo credit-information provider (spec section 5).

    Simulates the response an authorized provider would return. The values
    are randomized per profile but logically consistent, and deterministic:
    the seed comes from the declared profile only, so identical declared
    input always produces an identical record (the same invariant the
    telecom/wallet simulations follow).
    """

    provider_name = "mock"

    def fetch_credit_information(self, application: Application) -> dict:
        """The six mock credit-information fields for one application."""
        # seed from declared data only — never the application id, so two
        # identical profiles verify identically and score identically
        rng = random.Random(
            f"{application.age}|{application.monthly_income}"
            f"|{application.monthly_debt_payments}"
            f"|{application.digital_purchase_frequency}")
        monthly_debt = float(application.monthly_debt_payments)

        if monthly_debt <= 0:
            # no declared obligations: either never borrowed, or a previous
            # loan fully repaid on time (nothing outstanding today)
            if rng.random() < 0.55:
                return _credit_data(False, False, 0.0, 0, False, 0.0)
            on_time = rng.randint(GOOD_ON_TIME_THRESHOLD, 24)
            has_card = rng.random() < 0.4
            return _credit_data(True, has_card, 0.0, on_time, False, 0.0)

        # obligations exist: draw a repayment-behaviour profile, biased by the
        # declared debt burden (heavier burden -> weaker history) so demo
        # profiles stay realistic instead of independent noise
        burden = monthly_debt / max(float(application.monthly_income), 1.0)
        good_cut = max(0.72 - 1.1 * burden, 0.05)
        roll = rng.random()
        has_card = rng.random() < 0.6
        # total existing debt anchored on the declared monthly payment
        debt = round(monthly_debt * rng.randint(8, 24), -3)
        if roll < good_cut:
            return _credit_data(True, has_card, debt,
                                rng.randint(GOOD_ON_TIME_THRESHOLD, 24),
                                False, debt)
        if roll < good_cut + 0.28:
            return _credit_data(True, has_card, debt, rng.randint(1, 11),
                                False, debt)
        return _credit_data(True, has_card, debt, rng.randint(0, 6), True, debt)


# the active provider — replace with a real authorized service later
credit_verification_service = MockCreditVerificationService()


def verify_credit_history(db: Session, application: Application) -> dict:
    """Run the verification step, store the record and derive the category."""
    existing = (
        db.query(CreditVerification)
        .filter(CreditVerification.application_id == application.id)
        .first()
    )
    if existing is not None:
        raise ApiError(409, "credit_already_verified",
                       "Credit verification has already been completed for "
                       "this application")

    if application.status != "consented":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: "
            f"{STEP_ORDER} (credit verification runs after consent)")

    consent = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.application_id == application.id)
        .first()
    )
    if consent is None or not consent.credit_information_verification:
        raise ApiError(
            409, "credit_consent_required",
            "Credit information verification consent is required before "
            "credit history can be verified. " + CREDIT_CONSENT_TEXT)

    credit_data = credit_verification_service.fetch_credit_information(
        application)
    derived, inconsistent = derive_loan_history(credit_data)

    record = CreditVerification(
        application_id=application.id,
        provider=credit_verification_service.provider_name,
        derived_loan_history=derived,
        inconsistent=inconsistent,
        **credit_data,
    )
    db.add(record)
    # the derived category becomes the application's loan-history feature
    application.existing_loan_history = derived
    db.commit()

    return credit_verification_public(record)


def credit_verification_public(record: CreditVerification) -> dict:
    """API/PDF view of one stored verification record."""
    from interpretation import build_credit_history_explanation

    credit_data = {
        "has_previous_loan": record.has_previous_loan,
        "has_credit_card": record.has_credit_card,
        "total_outstanding_amount": record.total_outstanding_amount,
        "installments_paid_on_time": record.installments_paid_on_time,
        "has_overdue_or_default": record.has_overdue_or_default,
        "total_existing_debt": record.total_existing_debt,
    }
    return {
        "provider": record.provider,
        "demo_notice": DEMO_NOTICE,
        "credit_data": credit_data,
        "derived_loan_history": record.derived_loan_history,
        "inconsistent": record.inconsistent,
        "explanation": build_credit_history_explanation(
            credit_data, record.derived_loan_history),
        "created_at": (
            record.created_at.isoformat()
            if hasattr(record.created_at, "isoformat")
            else str(record.created_at) if record.created_at else None
        ),
    }
