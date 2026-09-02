"""Feature-builder gate: documented provider formulas, determinism, clamping.

The simulated telecom/wallet summaries implement the product's documented
weighted composites (see the "features calculation" design notes). These tests
pin the formulas, the training-range clamps and the determinism guarantee.
"""

import pytest

from backend.feature_builder import (
    PROVIDER_SIMULATION_NOTE, build_features, simulated_telecom_usage,
    simulated_wallet_activity,
)

MODEL_FEATURE_KEYS = {
    "age", "occupation", "monthly_income", "existing_loan_history",
    "debt_to_income_ratio", "loan_size", "telecom_usage_score",
    "mobile_wallet_activity", "digital_purchase_frequency", "psychometric_score",
}


class _Questionnaire:
    psychometric_score = 72.0


class FakeApplication:
    """Minimal application stand-in for build_features (no DB needed)."""

    def __init__(self, **overrides):
        values = dict(
            age=38, occupation="Self-Employed", monthly_income=65000.0,
            monthly_debt_payments=19500.0,
            existing_loan_history="No Previous Loan",
            requested_loan_size=500000.0, digital_purchase_frequency=5,
        )
        values.update(overrides)
        for key, value in values.items():
            setattr(self, key, value)
        self.questionnaire = _Questionnaire()


# ------------------------------------------------- documented weighted formulas

def test_telecom_formula_matches_documented_weights():
    # hand-computed: purchases=5, income=65000, age=38
    #   F1 = 5/10*100            = 50.0
    #   F2 = 60 + 0.4*50         = 80.0   (prepaid, consistency-adjusted)
    #   F3 = min(80/36, 1)*100   = 100.0  (age-18)*4 months, capped at 36
    #   F4 = 65000*0.02/2500*100 = 52.0
    #   composite = .30*50 + .20*80 + .25*100 + .25*52 = 69.0 -> 0.69
    assert simulated_telecom_usage(5, 65000, 38) == pytest.approx(0.69, abs=0.006)


def test_wallet_formula_matches_documented_weights():
    # hand-computed: purchases=5, income=65000, dti=0.3
    #   F1 = 5/12*100                = 41.67
    #   F2 = 65000*0.40/60000*100    = 43.33
    #   F3 = 2*(1-0.3)*50            = 70.0
    #   F4 = 5*4/24*100              = 83.33
    #   composite = .30*41.67 + .25*43.33 + .25*70 + .20*83.33 = 57.5 -> 0.575
    assert simulated_wallet_activity(5, 65000, 0.3) == pytest.approx(
        0.575, abs=0.006)


def test_provider_scores_clamped_to_training_range():
    # an extreme profile cannot leave the range the model saw in training
    assert simulated_telecom_usage(200, 5_000_000, 65) == 0.98
    assert simulated_wallet_activity(200, 5_000_000, 0.0) == 0.95
    # a minimal profile is clamped at the training floor
    assert simulated_telecom_usage(0, 1_000, 18) == 0.20
    assert simulated_wallet_activity(0, 1_000, 1.0) == 0.10


def test_provider_scores_increase_with_digital_activity():
    for purchases in (0, 3, 6, 12, 30):
        lower_t = simulated_telecom_usage(purchases, 65000, 38)
        higher_t = simulated_telecom_usage(purchases + 3, 65000, 38)
        lower_w = simulated_wallet_activity(purchases, 65000, 0.3)
        higher_w = simulated_wallet_activity(purchases + 3, 65000, 0.3)
        assert lower_t <= higher_t
        assert lower_w <= higher_w


def test_provider_note_documents_simulation_and_weights():
    note = PROVIDER_SIMULATION_NOTE.lower()
    assert "simulated" in note
    assert "30%" in note and "25%" in note and "20%" in note


# ------------------------------------------------------------ build_features

def test_build_features_provides_the_ten_model_features():
    features, warnings = build_features(FakeApplication())
    assert set(features) == MODEL_FEATURE_KEYS
    assert features["debt_to_income_ratio"] == pytest.approx(0.3, abs=1e-4)
    assert 0.0 <= features["telecom_usage_score"] <= 1.0
    assert 0.0 <= features["mobile_wallet_activity"] <= 1.0
    assert features["psychometric_score"] == 72.0
    assert features["telecom_usage_score"] == pytest.approx(0.69, abs=0.006)
    assert features["mobile_wallet_activity"] == pytest.approx(0.575, abs=0.006)
    assert warnings == []  # consistent profile -> no cross-field warnings


def test_build_features_is_deterministic():
    first = build_features(FakeApplication())
    second = build_features(FakeApplication())
    assert first == second


def test_cross_field_warnings_flag_inconsistent_profiles():
    inconsistent = FakeApplication(
        monthly_income=20000.0, monthly_debt_payments=0.0,
        existing_loan_history="Good Repayment History",
        requested_loan_size=500000.0,  # 25x income
    )
    _, warnings = build_features(inconsistent)
    assert any("24 times" in w for w in warnings)
    assert any("no monthly debt payments" in w for w in warnings)
