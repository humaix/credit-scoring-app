"""Spec §18 C — ML Pipeline.

Model loads successfully, valid input produces a numeric score, the score
stays within the expected range (even for extreme profiles) and identical
input always produces an identical prediction.
"""

from explanation_utils import MODEL_PATH, validate_applicant_data
from shap_explainer import _load_pipeline, assess_applicant

MODERATE_FEATURES = {
    "age": 38,
    "occupation": "Self-Employed",
    "monthly_income": 65000,
    "existing_loan_history": "No Previous Loan",
    "debt_to_income_ratio": 0.3,
    "loan_size": 500000,
    "telecom_usage_score": 0.69,
    "mobile_wallet_activity": 0.575,
    "digital_purchase_frequency": 5,
    "psychometric_score": 50.0,
}

MINIMUM_PROFILE = {  # every numeric feature at its least favourable extreme
    "age": 18,
    "occupation": "Daily Wage Worker",
    "monthly_income": 1000,
    "existing_loan_history": "Previous Default",
    "debt_to_income_ratio": 1.0,
    "loan_size": 10000000,
    "telecom_usage_score": 0.0,
    "mobile_wallet_activity": 0.0,
    "digital_purchase_frequency": 0,
    "psychometric_score": 0.0,
}

MAXIMUM_PROFILE = {  # every numeric feature at its most favourable extreme
    "age": 65,
    "occupation": "Business Owner",
    "monthly_income": 5000000,
    "existing_loan_history": "Good Repayment History",
    "debt_to_income_ratio": 0.0,
    "loan_size": 10000,
    "telecom_usage_score": 1.0,
    "mobile_wallet_activity": 1.0,
    "digital_purchase_frequency": 200,
    "psychometric_score": 100.0,
}


# ---------------------------------------------------- model loads successfully

def test_model_file_exists():
    assert MODEL_PATH.exists()
    assert MODEL_PATH.stat().st_size > 100_000  # a real trained pipeline


def test_saved_pipeline_loads_with_expected_steps():
    pipeline = _load_pipeline()
    assert "preprocess" in pipeline.named_steps
    assert "model" in pipeline.named_steps


# -------------------------------------------- valid input produces a score

def test_valid_input_produces_numeric_score():
    applicant = validate_applicant_data(MODERATE_FEATURES)
    result = assess_applicant(applicant)
    score = result["repayment_score"]
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
    assert result["score_category"] in (
        "Very Low", "Low", "Moderate", "High", "Very High")


def test_score_is_reported_to_one_decimal():
    applicant = validate_applicant_data(MODERATE_FEATURES)
    result = assess_applicant(applicant)
    assert result["repayment_score"] == round(result["repayment_score"], 1)


# --------------------------------------- score stays within expected range

def test_extreme_profiles_stay_within_zero_to_hundred():
    for profile in (MINIMUM_PROFILE, MAXIMUM_PROFILE):
        applicant = validate_applicant_data(profile)
        result = assess_applicant(applicant)
        assert 0.0 <= result["repayment_score"] <= 100.0, profile
        # raw model output is clipped, and the clip is recorded honestly
        assert result["raw_score"] <= 100.0 + 1e-6 or result["repayment_score"] == 100.0
        assert result["raw_score"] >= -1e-6 or result["repayment_score"] == 0.0


def test_extreme_profiles_order_sensibly():
    weak = assess_applicant(validate_applicant_data(MINIMUM_PROFILE))
    strong = assess_applicant(validate_applicant_data(MAXIMUM_PROFILE))
    assert strong["repayment_score"] > weak["repayment_score"]


# ------------------------------------------ same input -> same prediction

def test_identical_input_produces_identical_prediction():
    applicant = validate_applicant_data(MODERATE_FEATURES)
    first = assess_applicant(applicant)
    second = assess_applicant(validate_applicant_data(MODERATE_FEATURES))
    assert first["repayment_score"] == second["repayment_score"]
    assert first["all_contributions"] == second["all_contributions"]
    assert first["base_value"] == second["base_value"]


def test_validation_rejects_out_of_range_features():
    for field, bad_value in (
        ("age", 70), ("monthly_income", 0), ("debt_to_income_ratio", 1.5),
        ("telecom_usage_score", 1.2), ("psychometric_score", 101.0),
    ):
        try:
            validate_applicant_data({**MODERATE_FEATURES, field: bad_value})
        except ValueError:
            continue
        raise AssertionError(f"{field}={bad_value} should have been rejected")
