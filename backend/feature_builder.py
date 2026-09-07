"""Feature Builder — application + questionnaire + simulated providers -> features.

Assembles the exact ten model features an application needs, with a documented
source for each (see feature_sources.py). The telecom and wallet summaries are
SIMULATED provider outputs — no real operator or wallet provider is contacted.

Each simulated summary implements the product's documented weighted composite
(see the "features calculation" design notes):

  Telecom Score (0-100) = 0.30*F1 + 0.20*F2 + 0.25*F3 + 0.25*F4
    F1 recharge consistency  = min(purchases/10, 1) * 100
    F2 account type         = prepaid 60, adjusted toward 100 by consistency
    F3 SIM tenure           = min((age-18)*4 / 36, 1) * 100
    F4 avg recharge amount  = min(income*0.02 / 2500, 1) * 100

  Wallet Score (0-100) = 0.30*F1 + 0.25*F2 + 0.25*F3 + 0.20*F4
    F1 transaction frequency = min(purchases/12, 1) * 100
    F2 average balance       = min(income*0.40 / 60000, 1) * 100
    F3 inflow/outflow ratio  = min(2*(1 - debt_to_income) * 50, 100)
    F4 wallet account age    = min(purchases*4 / 24, 1) * 100

The composite is divided by 100 to reach the model's 0-1 feature scale and
clamped to the range the model saw in training. Every component is a
deterministic function of the applicant's declared profile, so identical
declared input always produces an identical score (no hidden randomness
anywhere in the demo). The component scores are also exposed (0-100 each) so
the applicant-facing "How is this calculated?" explanations show the real
calculation instead of inventing one.

Cross-field consistency checks (validation Layer 4) return warnings only:
they flag clearly inconsistent combinations for manual review and never
reject an applicant or change the score.
"""

from interpretation import PROVIDER_SIMULATION_NOTE  # single shared wording

from .models import Application

# training-distribution anchors for the simulated provider summaries
_TELECOM_MIN, _TELECOM_MAX = 0.20, 0.98
_WALLET_MIN, _WALLET_MAX = 0.10, 0.95


def telecom_component_scores(purchases: float, monthly_income: float,
                             age: int) -> dict:
    """The four documented telecom components, each on a 0-100 scale."""
    consistency = min(max(purchases, 0.0) / 10.0, 1.0) * 100.0
    return {
        "recharge_consistency": consistency,
        "account_type": 60.0 + 0.4 * consistency,  # prepaid, consistency-adjusted
        "sim_tenure": min(max(age - 18, 0) * 4.0 / 36.0, 1.0) * 100.0,
        "avg_recharge": min(max(monthly_income, 0.0) * 0.02 / 2500.0, 1.0) * 100.0,
    }


def wallet_component_scores(purchases: float, monthly_income: float,
                            debt_to_income: float) -> dict:
    """The four documented wallet components, each on a 0-100 scale."""
    return {
        "transaction_frequency": min(max(purchases, 0.0) / 12.0, 1.0) * 100.0,
        "average_balance": min(max(monthly_income, 0.0) * 0.40 / 60000.0, 1.0) * 100.0,
        "inflow_outflow": min(
            2.0 * (1.0 - min(max(debt_to_income, 0.0), 1.0)) * 50.0, 100.0),
        "account_age": min(max(purchases, 0.0) * 4.0 / 24.0, 1.0) * 100.0,
    }


def simulated_telecom_usage(purchases: float, monthly_income: float,
                            age: int) -> float:
    """Mock telecom provider summary, within the training range 0.20-0.98."""
    c = telecom_component_scores(purchases, monthly_income, age)
    composite = (0.30 * c["recharge_consistency"] + 0.20 * c["account_type"]
                 + 0.25 * c["sim_tenure"] + 0.25 * c["avg_recharge"])
    return round(min(max(composite / 100.0, _TELECOM_MIN), _TELECOM_MAX), 2)


def simulated_wallet_activity(purchases: float, monthly_income: float,
                              debt_to_income: float) -> float:
    """Mock wallet provider summary, within the training range 0.10-0.95."""
    c = wallet_component_scores(purchases, monthly_income, debt_to_income)
    composite = (0.30 * c["transaction_frequency"] + 0.25 * c["average_balance"]
                 + 0.25 * c["inflow_outflow"] + 0.20 * c["account_age"])
    return round(min(max(composite / 100.0, _WALLET_MIN), _WALLET_MAX), 2)


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
    debt_to_income = round(
        application.monthly_debt_payments / application.monthly_income, 4)
    features = {
        "age": application.age,
        "occupation": application.occupation,
        "monthly_income": application.monthly_income,
        "existing_loan_history": application.existing_loan_history,
        "debt_to_income_ratio": debt_to_income,
        "loan_size": application.requested_loan_size,
        "telecom_usage_score": simulated_telecom_usage(
            application.digital_purchase_frequency,
            application.monthly_income,
            application.age,
        ),
        "mobile_wallet_activity": simulated_wallet_activity(
            application.digital_purchase_frequency,
            application.monthly_income,
            debt_to_income,
        ),
        "digital_purchase_frequency": application.digital_purchase_frequency,
        "psychometric_score": application.questionnaire.psychometric_score,
    }
    return features, cross_field_warnings(application)
