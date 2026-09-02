"""Shared constants, validation and formatting for the explainability layer."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "final_credit_scoring_model.pkl"
REPORTS_DIR = Path(__file__).resolve().parent / "generated_reports"

NUM_FEATURES = [
    "age", "monthly_income", "debt_to_income_ratio", "loan_size",
    "telecom_usage_score", "mobile_wallet_activity",
    "digital_purchase_frequency", "psychometric_score",
]
CAT_FEATURES = ["occupation", "existing_loan_history"]
MODEL_FEATURES = NUM_FEATURES + CAT_FEATURES

# dataset columns that must never reach prediction or explanation
EXCLUDED_COLUMNS = ["borrower_id", "loan_history_code", "gender", "province"]

VALID_OCCUPATIONS = [
    "Salaried", "Self-Employed", "Business Owner",
    "Freelancer", "Daily Wage Worker", "Other",
]
VALID_LOAN_HISTORY = [
    "No Previous Loan", "Good Repayment History",
    "Delayed Repayment History", "Previous Default",
]

FEATURE_LABELS = {
    "age": "Age",
    "occupation": "Occupation",
    "monthly_income": "Monthly Income",
    "existing_loan_history": "Existing Loan History",
    "debt_to_income_ratio": "Debt-to-Income Ratio",
    "loan_size": "Loan Size",
    "telecom_usage_score": "Telecom Usage Score",
    "mobile_wallet_activity": "Mobile Wallet Activity",
    "digital_purchase_frequency": "Digital Purchase Frequency",
    "psychometric_score": "Psychometric Score",
}

# contiguous bands so no fractional score (e.g. 60.4) can fall between
# them and crash the flow; integer boundaries land in the lower band
CATEGORY_BOUNDS = [
    ("Very Low", 0.0, 20.0), ("Low", 20.0, 40.0), ("Moderate", 40.0, 60.0),
    ("High", 60.0, 80.0), ("Very High", 80.0, 100.0),
]

# numeric validation ranges: (min, max, integral)
NUMERIC_RANGES = {
    "age": (18, 65, True),
    "monthly_income": (1_000, 5_000_000, False),
    "debt_to_income_ratio": (0.0, 1.0, False),
    "loan_size": (10_000, 10_000_000, False),
    "telecom_usage_score": (0.0, 1.0, False),
    "mobile_wallet_activity": (0.0, 1.0, False),
    "digital_purchase_frequency": (0, 200, True),
    "psychometric_score": (0.0, 100.0, False),
}

SAMPLE_APPLICANTS = [
    {
        "label": "High profile",
        "data": {
            "age": 45, "occupation": "Business Owner", "monthly_income": 120_000,
            "existing_loan_history": "Good Repayment History",
            "debt_to_income_ratio": 0.12, "loan_size": 300_000,
            "telecom_usage_score": 0.85, "mobile_wallet_activity": 0.88,
            "digital_purchase_frequency": 8, "psychometric_score": 78.0,
        },
    },
    {
        "label": "Moderate profile",
        "data": {
            "age": 38, "occupation": "Self-Employed", "monthly_income": 65_000,
            "existing_loan_history": "No Previous Loan",
            "debt_to_income_ratio": 0.30, "loan_size": 500_000,
            "telecom_usage_score": 0.62, "mobile_wallet_activity": 0.55,
            "digital_purchase_frequency": 5, "psychometric_score": 58.0,
        },
    },
    {
        "label": "Low profile",
        "data": {
            "age": 26, "occupation": "Daily Wage Worker", "monthly_income": 28_000,
            "existing_loan_history": "Previous Default",
            "debt_to_income_ratio": 0.55, "loan_size": 350_000,
            "telecom_usage_score": 0.35, "mobile_wallet_activity": 0.28,
            "digital_purchase_frequency": 2, "psychometric_score": 35.0,
        },
    },
]


def score_category(score):
    for label, low, high in CATEGORY_BOUNDS:
        if low <= score <= high:
            return label
    raise ValueError(f"score {score} is outside 0-100")


def format_feature_value(name, value):
    """Human-readable display of a raw feature value."""
    if name in ("monthly_income", "loan_size"):
        return f"PKR {value:,.0f}"
    if name in ("debt_to_income_ratio", "telecom_usage_score", "mobile_wallet_activity"):
        return f"{value:.2f}"
    if name == "psychometric_score":
        return f"{value:.1f}"
    if name == "age":
        return f"{value} years"
    if name == "digital_purchase_frequency":
        return f"{value} per month"
    return str(value)


def validate_applicant_data(data):
    """Validate raw applicant input; return a normalized feature dict.

    Raises ValueError listing every problem found. Values are never modified
    silently - invalid input is rejected, not coerced into range.
    """
    if not isinstance(data, dict):
        raise ValueError("applicant data must be a dictionary of feature values")

    unknown = [k for k in data if k not in MODEL_FEATURES and k not in EXCLUDED_COLUMNS]
    if unknown:
        raise ValueError(
            f"unknown field(s): {unknown}. Accepted fields: {MODEL_FEATURES} "
            f"(dataset-only columns {EXCLUDED_COLUMNS} are ignored)"
        )

    errors = []
    for key in MODEL_FEATURES:
        if key not in data or data[key] is None:
            errors.append(f"missing required field: {key}")
    present = [k for k in MODEL_FEATURES if k in data and data[k] is not None]

    normalized = {}
    for key in present:
        value = data[key]
        if key in NUMERIC_RANGES:
            low, high, integral = NUMERIC_RANGES[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"{key}: expected a number, got {value!r}")
                continue
            if integral and not float(value).is_integer():
                errors.append(f"{key}: expected a whole number, got {value!r}")
                continue
            if not (low <= value <= high):
                errors.append(f"{key}: {value!r} is outside the valid range [{low}, {high}]")
                continue
            normalized[key] = int(value) if integral else float(value)
        else:
            allowed = VALID_OCCUPATIONS if key == "occupation" else VALID_LOAN_HISTORY
            if not isinstance(value, str) or value not in allowed:
                errors.append(f"{key}: {value!r} is not one of {allowed}")
                continue
            normalized[key] = value

    if errors:
        raise ValueError("invalid applicant data:\n  - " + "\n  - ".join(errors))

    return {k: normalized[k] for k in MODEL_FEATURES}
