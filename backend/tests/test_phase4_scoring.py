"""Phase 4 gate: end-to-end scoring, PDF report, LLM fallback, model safety."""

import hashlib
import io
import itertools

import pytest
from pypdf import PdfReader

import backend.scoring as scoring_module
from backend.questionnaire import QUESTIONS
from explanation_utils import score_category
from llm_explainer import fallback_explanation

STRONG = {
    "age": 45, "occupation": "Business Owner", "monthly_income": 120000,
    "monthly_debt_payments": 14400,
    "existing_loan_history": "Good Repayment History",
    "requested_loan_size": 300000, "digital_purchase_frequency": 8,
}
MODERATE = {
    "age": 38, "occupation": "Self-Employed", "monthly_income": 65000,
    "monthly_debt_payments": 19500,
    "existing_loan_history": "No Previous Loan",
    "requested_loan_size": 500000, "digital_purchase_frequency": 5,
}
WEAK = {
    "age": 26, "occupation": "Daily Wage Worker", "monthly_income": 28000,
    "monthly_debt_payments": 15400,
    "existing_loan_history": "Previous Default",
    "requested_loan_size": 350000, "digital_purchase_frequency": 2,
}

_identity_counter = itertools.count(9000)


def _unique_identity():
    n = next(_identity_counter)
    return {
        "full_name": "Hina Raza",
        "cnic": f"35202-{n:07d}-7",
        "mobile": "03111234567",
    }


def _answers(orientation):
    """Likert answers producing a high / mid / low psychometric score."""
    if orientation == "high":
        return [5 if not q["reversed"] else 1 for q in QUESTIONS]   # 100.0
    if orientation == "low":
        return [2 if not q["reversed"] else 4 for q in QUESTIONS]   # 25.0
    return [3] * 12                                                 # 50.0


@pytest.fixture()
def offline_explanations(monkeypatch):
    """Tests never call the live LLM — deterministic fallback templates."""
    monkeypatch.setattr(
        scoring_module, "generate_natural_language_explanation",
        fallback_explanation)


def _full_flow(client, payload, answers):
    """register -> application -> verify -> consent -> questionnaire."""
    response = client.post("/api/auth/register", json=_unique_identity())
    assert response.status_code == 200, response.text
    headers = {"X-Session-Token": response.json()["session_token"]}

    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    application_id = response.json()["application_id"]

    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()
    response = client.post("/api/verification/verify-otp",
                           json={"application_id": application_id,
                                 "code": otp["simulated_otp"]},
                           headers=headers)
    assert response.json()["status"] == "verified"

    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 200, response.text

    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": answers},
                           headers=headers)
    assert response.status_code == 200, response.text
    return headers, application_id


def _score(client, headers, application_id):
    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------- e2e profiles

def test_strong_moderate_weak_profiles_score_correctly(client, offline_explanations):
    scores = {}
    for label, payload, orientation in (
        ("strong", STRONG, "high"),
        ("moderate", MODERATE, "mid"),
        ("weak", WEAK, "low"),
    ):
        headers, application_id = _full_flow(client, payload, _answers(orientation))
        result = _score(client, headers, application_id)
        scores[label] = result

        score = result["repayment_score"]
        assert 0 <= score <= 100, (label, score)
        assert result["score_category"] == score_category(score)
        assert result["status"] == "scored"
        assert result["explanation_source"] == "fallback"
        assert result["report_filename"].startswith(
            f"repayment_assessment_app{application_id}_")

        # contributor structure: signs correct, at most three per side
        # (an extreme profile can legitimately have zero contributors on
        # one side — the report renders an explicit note for that case)
        assert 0 <= len(result["positive_contributors"]) <= 3
        assert 0 <= len(result["negative_contributors"]) <= 3
        assert all(c["shap_value"] > 0 for c in result["positive_contributors"])
        assert all(c["shap_value"] < 0 for c in result["negative_contributors"])
        assert len(result["all_contributions"]) == 10

        # explanation wording driven by the actual contributions
        explanation = result["explanation"]
        assert explanation["source"] == "fallback"
        assert str(int(score)) in explanation["summary"] or f"{score}" in explanation["summary"]

        # responsible-AI disclaimer travels with every score
        assert "not a guaranteed probability" in result["disclaimer"]
        assert "simulated" in result["provider_note"].lower()

        # application detail reflects the scored state
        detail = client.get(f"/api/applications/{application_id}",
                            headers=headers).json()
        assert detail["status"] == "scored"
        assert detail["assessment"]["repayment_score"] == score
        assert detail["assessment"]["score_category"] == result["score_category"]

    # the model ranks the three profiles in the expected order
    assert scores["strong"]["repayment_score"] > scores["moderate"]["repayment_score"]
    assert scores["moderate"]["repayment_score"] > scores["weak"]["repayment_score"]


def test_pdf_report_matches_api_result(client, offline_explanations):
    headers, application_id = _full_flow(client, MODERATE, _answers("mid"))
    scoring = _score(client, headers, application_id)

    response = client.get(f"/api/applications/{application_id}/report",
                          headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"

    text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages
    )
    # the PDF shows exactly the API's score and category
    assert f"{scoring['repayment_score']:.1f}" in text
    assert scoring["score_category"] in text
    # disclaimer present, internal terminology absent
    assert "synthetic dataset" in text.lower()
    for forbidden in ("occupation_", "existing_loan_history_", "SHAP"):
        assert forbidden not in text


def test_scoring_state_and_authorization_errors(client, offline_explanations):
    # unauthenticated
    response = client.post("/api/scoring/predict", json={"application_id": 1})
    assert response.status_code == 401

    headers, application_id = _full_flow(client, MODERATE, _answers("mid"))

    # another applicant cannot score or read someone else's application
    other = client.post("/api/auth/register", json=_unique_identity()).json()
    other_headers = {"X-Session-Token": other["session_token"]}
    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=other_headers)
    assert response.status_code == 404
    response = client.get(f"/api/applications/{application_id}/report",
                          headers=other_headers)
    assert response.status_code == 404

    # report before scoring
    response = client.get(f"/api/applications/{application_id}/report",
                          headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_scored"

    _score(client, headers, application_id)

    # double scoring is rejected
    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_scored"


def test_scoring_requires_completed_assessment(client, offline_explanations):
    # walk the flow only up to consent (no questionnaire yet)
    response = client.post("/api/auth/register", json=_unique_identity())
    headers = {"X-Session-Token": response.json()["session_token"]}
    application_id = client.post(
        "/api/applications", json=MODERATE, headers=headers
    ).json()["application_id"]
    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()
    client.post("/api/verification/verify-otp",
                json={"application_id": application_id,
                      "code": otp["simulated_otp"]}, headers=headers)
    client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)

    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cross_field_warnings_never_block_scoring(client, offline_explanations):
    inconsistent = {
        "age": 40, "occupation": "Salaried", "monthly_income": 20000,
        "monthly_debt_payments": 0,
        "existing_loan_history": "Good Repayment History",
        "requested_loan_size": 500000,  # 25x income -> warning
        "digital_purchase_frequency": 4,
    }
    headers, application_id = _full_flow(client, inconsistent, _answers("mid"))
    result = _score(client, headers, application_id)

    # both inconsistencies are flagged for manual review...
    assert any("24 times" in w for w in result["consistency_warnings"])
    assert any("no monthly debt payments" in w for w in result["consistency_warnings"])
    # ...but scoring still completes
    assert result["status"] == "scored"
    assert 0 <= result["repayment_score"] <= 100


# ------------------------------------------------- determinism and safety

def test_identical_input_identical_prediction(client, offline_explanations):
    """Two applications with identical declared data must score identically."""
    results = []
    for _ in range(2):
        headers, application_id = _full_flow(client, MODERATE, _answers("mid"))
        results.append(_score(client, headers, application_id))
    assert results[0]["repayment_score"] == results[1]["repayment_score"]
    assert results[0]["all_contributions"] == results[1]["all_contributions"]


def test_model_file_is_never_modified(client, offline_explanations):
    from backend.scoring import REPORTS_DIR
    model_path = REPORTS_DIR.parent / "models" / "final_credit_scoring_model.pkl"
    before = hashlib.md5(model_path.read_bytes()).hexdigest()

    headers, application_id = _full_flow(client, MODERATE, _answers("mid"))
    _score(client, headers, application_id)

    after = hashlib.md5(model_path.read_bytes()).hexdigest()
    assert before == after


def test_llm_outage_falls_back_deterministically(client, monkeypatch):
    """Simulated LLM outage -> SHAP-driven fallback, direction preserved."""
    import llm_explainer

    def _unavailable(*args, **kwargs):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(llm_explainer, "_post_chat_completion", _unavailable)

    assessment = {
        "repayment_score": 60.0, "raw_score": 60.0, "score_category": "Moderate",
        "applicant_features": [],
        "positive_contributors": [
            {"feature": "Monthly Income", "value": "PKR 80,000",
             "shap_value": 6.0}],
        "negative_contributors": [
            {"feature": "Debt-to-Income Ratio", "value": "0.42",
             "shap_value": -4.0}],
        "all_contributions": [], "base_value": 58.0,
    }
    result = llm_explainer.generate_natural_language_explanation(assessment)
    assert result["source"] == "fallback"
    assert "60.0/100" in result["summary"]
    assert "PKR 80,000" in result["positive_factors"][0]
    assert "positive contribution" in result["positive_factors"][0]
    assert "negative contribution" in result["negative_factors"][0]
    assert result["overall_explanation"]
