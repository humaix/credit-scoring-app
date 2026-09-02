"""Spec §18 D — SHAP explanations.

Contribution direction is preserved, the SHAP decomposition reconstructs the
model output within tolerance, and one-hot categorical columns are aggregated
back to human-readable features.
"""

from explanation_utils import FEATURE_LABELS, MODEL_FEATURES, validate_applicant_data
from shap_explainer import assess_applicant

APPLICANT = validate_applicant_data({
    "age": 42,
    "occupation": "Business Owner",
    "monthly_income": 90000,
    "existing_loan_history": "Delayed Repayment History",
    "debt_to_income_ratio": 0.35,
    "loan_size": 450000,
    "telecom_usage_score": 0.72,
    "mobile_wallet_activity": 0.61,
    "digital_purchase_frequency": 7,
    "psychometric_score": 66.0,
})


def _assessment():
    # a fresh assessment per test keeps each one independent
    return assess_applicant(validate_applicant_data(dict(APPLICANT)))


# ------------------------------------------- contribution direction preserved

def test_positive_contributors_have_positive_shap_values():
    result = _assessment()
    assert all(c["shap_value"] > 0 for c in result["positive_contributors"])


def test_negative_contributors_have_negative_shap_values():
    result = _assessment()
    assert all(c["shap_value"] < 0 for c in result["negative_contributors"])


def test_top_three_per_side_and_sorted_by_magnitude():
    result = _assessment()
    positives = result["positive_contributors"]
    negatives = result["negative_contributors"]
    assert len(positives) <= 3
    assert len(negatives) <= 3
    assert positives == sorted(
        positives, key=lambda c: c["shap_value"], reverse=True)
    assert negatives == sorted(negatives, key=lambda c: c["shap_value"])


# -------------------------------- reconstruction matches model output

def test_shap_reconstruction_matches_model_output():
    """base_value + all contributions must rebuild the raw prediction."""
    result = _assessment()
    total = result["base_value"] + sum(
        c["shap_value"] for c in result["all_contributions"])
    assert abs(total - result["raw_score"]) < 1e-2


def test_displayed_score_is_clipped_raw_prediction():
    result = _assessment()
    assert abs(result["repayment_score"] - result["raw_score"]) < 0.06


# ------------------------------------------------ categorical aggregation

def test_one_hot_columns_aggregate_to_human_readable_features():
    result = _assessment()
    features = [c["feature"] for c in result["all_contributions"]]
    assert len(features) == len(MODEL_FEATURES)
    assert set(features) == set(FEATURE_LABELS.values())


def test_no_encoded_feature_names_surface():
    result = _assessment()
    blob = str(result)
    for forbidden in ("occupation_", "existing_loan_history_", "x0_", "num__"):
        assert forbidden not in blob


def test_categorical_contribution_labels_show_actual_level():
    """The aggregated Occupation / Loan History rows carry the applicant's
    actual level as their value, not an encoded column name."""
    result = _assessment()
    by_feature = {c["feature"]: c for c in result["all_contributions"]}
    assert by_feature["Occupation"]["value"] == "Business Owner"
    assert by_feature["Existing Loan History"]["value"] == "Delayed Repayment History"


def test_applicant_features_list_covers_all_ten_features():
    result = _assessment()
    listed = [f["feature"] for f in result["applicant_features"]]
    assert listed == [FEATURE_LABELS[name] for name in MODEL_FEATURES]
    values = {f["feature"]: f["value"] for f in result["applicant_features"]}
    assert values["Monthly Income"] == "PKR 90,000"
    assert values["Debt-to-Income Ratio"] == "0.35"
