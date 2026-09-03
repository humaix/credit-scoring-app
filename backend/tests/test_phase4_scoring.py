"""Phase 4 gate: end-to-end scoring, PDF report, LLM fallback, model safety."""

import hashlib
import io

from pypdf import PdfReader

from backend.scoring import REPORTS_DIR
from backend.tests.flow import (
    MODERATE, STRONG, WEAK, full_flow, likert_answers, score,
    submit_employment, unique_identity,
)
from explanation_utils import score_category


def _full_flow(client, payload, answers):
    return full_flow(client, payload, answers)


def _score(client, headers, application_id):
    return score(client, headers, application_id)


# ------------------------------------------------------------- e2e profiles

def test_strong_moderate_weak_profiles_score_correctly(client, offline_explanations):
    scores = {}
    for label, payload, orientation in (
        ("strong", STRONG, "high"),
        ("moderate", MODERATE, "mid"),
        ("weak", WEAK, "low"),
    ):
        headers, application_id = _full_flow(client, payload, likert_answers(orientation))
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

        # application detail reflects the scored state and carries the full
        # persisted assessment (identical to what the scoring run returned)
        detail = client.get(f"/api/applications/{application_id}",
                            headers=headers).json()
        assert detail["status"] == "scored"
        assert detail["assessment"]["repayment_score"] == score
        assert detail["assessment"]["score_category"] == result["score_category"]
        assert detail["assessment"]["base_value"] == result["base_value"]
        assert (detail["assessment"]["all_contributions"]
                == result["all_contributions"])
        assert (detail["assessment"]["positive_contributors"]
                == result["positive_contributors"])
        assert (detail["assessment"]["negative_contributors"]
                == result["negative_contributors"])
        assert detail["assessment"]["explanation"] == result["explanation"]

    # the model ranks the three profiles in the expected order
    assert scores["strong"]["repayment_score"] > scores["moderate"]["repayment_score"]
    assert scores["moderate"]["repayment_score"] > scores["weak"]["repayment_score"]


def test_pdf_report_matches_api_result(client, offline_explanations):
    headers, application_id = _full_flow(client, MODERATE, likert_answers("mid"))
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

    headers, application_id = _full_flow(client, MODERATE, likert_answers("mid"))

    # another applicant cannot score or read someone else's application
    other = client.post("/api/auth/register", json=unique_identity()).json()
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
    response = client.post("/api/auth/register", json=unique_identity())
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
    submit_employment(client, headers, application_id, MODERATE)
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
        "has_bank_account": False,
    }
    headers, application_id = _full_flow(client, inconsistent, likert_answers("mid"))
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
        headers, application_id = _full_flow(client, MODERATE, likert_answers("mid"))
        results.append(_score(client, headers, application_id))
    assert results[0]["repayment_score"] == results[1]["repayment_score"]
    assert results[0]["all_contributions"] == results[1]["all_contributions"]


def test_model_file_is_never_modified(client, offline_explanations):
    model_path = REPORTS_DIR.parent / "models" / "final_credit_scoring_model.pkl"
    before = hashlib.md5(model_path.read_bytes()).hexdigest()

    headers, application_id = _full_flow(client, MODERATE, likert_answers("mid"))
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
