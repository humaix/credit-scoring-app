"""Feature Builder — application + questionnaire + simulated providers -> features.

Assembles the exact ten model features an application needs, with a documented
source for each (see feature_sources.py). The telecom and wallet summaries are
SIMULATED provider outputs — no real operator or wallet provider is contacted.
They are deterministic functions of the applicant's declared digital activity,
so identical declared input always produces an identical score (no hidden
randomness anywhere in the demo).

Cross-field consistency checks (validation Layer 4) return warnings only:
they flag clearly inconsistent combinations for manual review and never
reject an applicant or change the score.
"""

from .models import Application

# training-distribution anchors for the simulated provider summaries
_TELECOM_MIN, _TELECOM_MAX = 0.20, 0.98
_WALLET_MIN, _WALLET_MAX = 0.10, 0.95
_DIGITAL_SATURATION = 45  # purchases/month at which digital intensity saturates

PROVIDER_SIMULATION_NOTE = (
    "Telecom and wallet summaries are simulated for this prototype (no real "
    "provider is contacted) and are derived deterministically from the "
    "applicant's declared digital activity."
)


def _digital_intensity(purchases: float) -> float:
    """Saturating 0-1 measure of declared digital activity.

    1 - exp(-purchases/6) mirrors the concave digital-activity relationship
    observed during EDA: activity helps, with diminishing returns.
    """
    purchases = max(float(purchases), 0.0)
    return 1.0 - pow(2.718281828459045, -purchases / 6.0)


def simulated_telecom_usage(purchases: float) -> float:
    """Mock telecom provider summary, within the training range 0.20-0.98."""
    intensity = _digital_intensity(purchases)
    return round(_TELECOM_MIN + (_TELECOM_MAX - _TELECOM_MIN) * intensity, 2)


def simulated_wallet_activity(purchases: float) -> float:
    """Mock wallet provider summary, within the training range 0.10-0.95."""
    intensity = _digital_intensity(purchases)
    return round(_WALLET_MIN + (_WALLET_MAX - _WALLET_MIN) * intensity, 2)


def cross_field_warnings(application: Application) -> list:
    """Layer 4: clearly inconsistent combinations -> warnings, never rejection."""
    warnings = []
    if application.requested_loan_size > 24 * application.monthly_income:
        warnings.append(
            "Requested loan size is more than 24 times the declared monthly "
            "income - manual review recommended.")
    if (application.monthly_debt_payments == 0
            and application.existing_loan_history != "No Previous Loan"):
        warnings.append(
            "Declared loan history suggests existing obligations, but no "
            "monthly debt payments were declared - please review.")
    return warnings


def build_features(application: Application) -> tuple:
    """Assemble the ten model features for an application past assessment.

    Returns (features dict, cross-field consistency warnings).
    """
    features = {
        "age": application.age,
        "occupation": application.occupation,
        "monthly_income": application.monthly_income,
        "existing_loan_history": application.existing_loan_history,
        "debt_to_income_ratio": round(
            application.monthly_debt_payments / application.monthly_income, 4),
        "loan_size": application.requested_loan_size,
        "telecom_usage_score": simulated_telecom_usage(
            application.digital_purchase_frequency),
        "mobile_wallet_activity": simulated_wallet_activity(
            application.digital_purchase_frequency),
        "digital_purchase_frequency": application.digital_purchase_frequency,
        "psychometric_score": application.questionnaire.psychometric_score,
    }
    return features, cross_field_warnings(application)
