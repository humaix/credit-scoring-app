"""Spec §18 H — End-to-end journeys.

Every applicant archetype the spec calls out, driven through the complete
API flow: strong / moderate / weak profiles, invalid applicant input,
failed verification (wrong OTP and simulated registry miss) and LLM
unavailability. Scoring uses the deterministic offline wording layer.
"""

import pytest

from backend.tests.flow import (
    MODERATE, STRONG, WEAK, full_flow, likert_answers, score, unique_identity,
)
from explanation_utils import score_category


def _journey(client, payload, orientation):
    """Complete journey: registration through the downloadable PDF report."""
    headers, application_id = full_flow(client, payload,
                                        likert_answers(orientation))
    result = score(client, headers, application_id)
    report = client.get(f"/api/applications/{application_id}/report",
                        headers=headers)
    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    return result, report, detail


# --------------------------------------------------------- applicant profiles

@pytest.mark.parametrize("label,payload,orientation", [
    ("strong", STRONG, "high"),
    ("moderate", MODERATE, "mid"),
    ("weak", WEAK, "low"),
])
def test_profile_completes_the_full_journey(client, offline_explanations,
                                            label, payload, orientation):
    result, report, detail = _journey(client, payload, orientation)

    assert result["status"] == "scored"
    assert 0 <= result["repayment_score"] <= 100
    assert result["score_category"] == score_category(result["repayment_score"])
    assert result["explanation"]["summary"]
    assert "not a guaranteed probability" in result["disclaimer"]
    assert "simulated" in result["provider_note"].lower()

    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content[:5] == b"%PDF-"

    assert detail["status"] == "scored"
    assert detail["assessment"]["repayment_score"] == result["repayment_score"]
    assert detail["assessment"]["explanation"] == result["explanation"]


def test_profiles_rank_strong_above_moderate_above_weak(client, offline_explanations):
    scores = {}
    for label, payload, orientation in (
        ("strong", STRONG, "high"),
        ("moderate", MODERATE, "mid"),
        ("weak", WEAK, "low"),
    ):
        result, _, _ = _journey(client, payload, orientation)
        scores[label] = result["repayment_score"]

    assert scores["strong"] > scores["moderate"] > scores["weak"]


# --------------------------------------------------- invalid applicant input

def test_invalid_applicant_input_never_enters_the_flow(client):
    registered = client.post("/api/auth/register", json=unique_identity()).json()
    headers = {"X-Session-Token": registered["session_token"]}

    invalid_payloads = [
        {**MODERATE, "age": 17},                     # below the model's age range
        {**MODERATE, "occupation": "Astronaut"},     # unknown category
        {**MODERATE, "monthly_income": 500},         # below the model's income range
        {**MODERATE, "digital_purchase_frequency": 2.5},  # non-integer
    ]
    for payload in invalid_payloads:
        response = client.post("/api/applications", json=payload,
                               headers=headers)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "validation_error"

    # nothing was created, so the journey cannot even start
    assert client.get("/api/applications", headers=headers).json() == []
    response = client.post("/api/verification/request-otp",
                           json={"application_id": 1}, headers=headers)
    assert response.status_code == 404


# ------------------------------------------------------ failed verification

def test_registry_miss_fails_verification_and_blocks_the_flow(client):
    """A correct OTP for an identity the simulated registry cannot match
    ends the journey at 'created' — consent and scoring are refused."""
    registered = client.post(
        "/api/auth/register", json=unique_identity("00000")).json()
    headers = {"X-Session-Token": registered["session_token"]}
    application_id = client.post(
        "/api/applications", json=MODERATE, headers=headers
    ).json()["application_id"]

    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()
    response = client.post("/api/verification/verify-otp",
                           json={"application_id": application_id,
                                 "code": otp["simulated_otp"]},
                           headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "no matching record" in body["message"]

    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["status"] == "created"
    assert detail["verification"]["status"] == "failed"

    # every later step is refused while verification stands failed
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"

    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 409


def test_wrong_otp_counts_down_locks_out_and_recovers(client):
    registered = client.post("/api/auth/register", json=unique_identity()).json()
    headers = {"X-Session-Token": registered["session_token"]}
    application_id = client.post(
        "/api/applications", json=MODERATE, headers=headers
    ).json()["application_id"]

    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()

    # each wrong code decrements the remaining attempts (max 5)
    for expected_remaining in (4, 3, 2, 1):
        response = client.post(
            "/api/verification/verify-otp",
            json={"application_id": application_id, "code": "000000"},
            headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["attempts_remaining"] == expected_remaining

    # the fifth wrong attempt locks the verification record
    response = client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": "000000"},
        headers=headers)
    assert response.json()["status"] == "failed"

    # even the correct code is refused while locked...
    response = client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": otp["simulated_otp"]},
        headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_pending_otp"

    # ...but requesting a fresh OTP restarts verification cleanly
    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()
    response = client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": otp["simulated_otp"]},
        headers=headers)
    assert response.json()["status"] == "verified"


# -------------------------------------------------------- LLM unavailable

def test_llm_unavailable_journey_still_completes(client, offline_explanations):
    """The wording layer going down never blocks scoring: the deterministic
    SHAP-driven fallback explains the very same assessment."""
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    result = score(client, headers, application_id)

    assert result["status"] == "scored"
    assert result["explanation_source"] == "fallback"
    explanation = result["explanation"]
    assert explanation["source"] == "fallback"
    assert str(result["repayment_score"]) in explanation["summary"]
    assert explanation["positive_factors"] or explanation["negative_factors"]

    # the report is still produced with the fallback wording
    report = client.get(f"/api/applications/{application_id}/report",
                        headers=headers)
    assert report.status_code == 200
    assert report.content[:5] == b"%PDF-"

    # and the persisted assessment is served identically afterwards
    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["assessment"]["explanation"] == explanation
