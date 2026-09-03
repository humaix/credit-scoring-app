"""Phase 3 gate: OTP verification flow, consent gating, questionnaire scoring."""

import itertools

from backend import config
from backend.questionnaire import CONSISTENCY_PAIRS, QUESTIONS, score_questionnaire
from backend.tests.flow import cnic_image_b64, submit_employment

VALID_APPLICATION = {
    "age": 35,
    "occupation": "Salaried",
    "monthly_income": 60000,
    "monthly_debt_payments": 18000,
    "existing_loan_history": "No Previous Loan",
    "requested_loan_size": 400000,
    "digital_purchase_frequency": 6,
    "has_bank_account": False,
}

_identity_counter = itertools.count(5000)


def _unique_identity(cnic_prefix="42201"):
    n = next(_identity_counter)
    return {
        "full_name": "Usman Tariq",
        "cnic": f"{cnic_prefix}-{n:07d}-3",
        "email": f"usman{n}@example.com",
        "mobile": "03451234567",
        "password": "Roshan123",
        "confirm_password": "Roshan123",
        "cnic_front_image": cnic_image_b64(),
        "cnic_back_image": cnic_image_b64(),
    }


def _register_and_apply(client, identity=None):
    """Register an applicant and create their loan application."""
    identity = identity or _unique_identity()
    response = client.post("/api/auth/register", json=identity)
    assert response.status_code == 200, response.text
    headers = {"X-Session-Token": response.json()["session_token"]}
    response = client.post(
        "/api/applications", json=VALID_APPLICATION, headers=headers)
    assert response.status_code == 201, response.text
    return headers, response.json()["application_id"]


def _request_otp(client, headers, application_id):
    response = client.post(
        "/api/verification/request-otp",
        json={"application_id": application_id}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _verify_otp(client, headers, application_id, code):
    return client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": code},
        headers=headers)


def _grant_full_consent(client, headers, application_id):
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _complete_through_consent(client):
    """Walk an application up to the 'consented' step."""
    headers, application_id = _register_and_apply(client)
    otp = _request_otp(client, headers, application_id)
    assert _verify_otp(client, headers, application_id,
                      otp["simulated_otp"]).json()["status"] == "verified"
    submit_employment(client, headers, application_id, VALID_APPLICATION)
    _grant_full_consent(client, headers, application_id)
    return headers, application_id


# ----------------------------------------------------------------- OTP flow

def test_otp_request_and_verification(client):
    headers, application_id = _register_and_apply(client)

    otp = _request_otp(client, headers, application_id)
    assert otp["status"] == "pending"
    assert otp["notice"].startswith("Simulated OTP")
    assert len(otp["simulated_otp"]) == 6  # DEV_RETURN_OTP demo mode
    # identifiers never travel with the OTP response
    assert "03451234567" not in str(otp)

    # application detail exposes the pending verification record
    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["verification"]["status"] == "pending"
    assert detail["verification"]["provider"] == "mock"
    assert detail["status"] == "created"

    response = _verify_otp(client, headers, application_id, otp["simulated_otp"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "verified"

    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["status"] == "verified"
    assert detail["verification"]["status"] == "verified"

    # re-requesting after verification is a state error
    response = client.post("/api/verification/request-otp",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_otp_wrong_codes_lock_out_then_new_otp_works(client):
    headers, application_id = _register_and_apply(client)
    otp = _request_otp(client, headers, application_id)

    # wrong codes consume attempts one by one
    for attempt in range(config.OTP_MAX_ATTEMPTS - 1):
        response = _verify_otp(client, headers, application_id, "000000")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["attempts_remaining"] == config.OTP_MAX_ATTEMPTS - attempt - 1

    # the final wrong code locks the record
    response = _verify_otp(client, headers, application_id, "000000")
    assert response.json()["status"] == "failed"

    # even the correct code no longer works
    response = _verify_otp(client, headers, application_id, otp["simulated_otp"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_pending_otp"

    # ...but a fresh OTP restarts the flow cleanly
    otp = _request_otp(client, headers, application_id)
    response = _verify_otp(client, headers, application_id, otp["simulated_otp"])
    assert response.json()["status"] == "verified"


def test_otp_expiry_fails_verification(client, monkeypatch):
    monkeypatch.setattr(config, "OTP_TTL_SECONDS", -1)
    headers, application_id = _register_and_apply(client)
    otp = _request_otp(client, headers, application_id)

    response = _verify_otp(client, headers, application_id, otp["simulated_otp"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "otp_expired_or_locked"

    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["verification"]["status"] == "failed"


def test_simulated_identity_miss_fails_verification(client):
    # CNICs starting 00000 never match the simulated registry
    headers, application_id = _register_and_apply(
        client, _unique_identity(cnic_prefix="00000"))
    otp = _request_otp(client, headers, application_id)

    response = _verify_otp(client, headers, application_id, otp["simulated_otp"])
    body = response.json()
    assert body["status"] == "failed"
    assert "Simulated identity check" in body["message"]

    # application stays at 'created' so a corrected retry is possible
    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["status"] == "created"


def test_verification_requires_session_and_ownership(client):
    headers, application_id = _register_and_apply(client)

    response = client.post("/api/verification/request-otp",
                           json={"application_id": application_id})
    assert response.status_code == 401

    # another applicant's application is invisible (404, not 403)
    other = client.post("/api/auth/register", json=_unique_identity()).json()
    response = client.post(
        "/api/verification/request-otp",
        json={"application_id": application_id},
        headers={"X-Session-Token": other["session_token"]})
    assert response.status_code == 404

    # unknown application id
    response = client.post("/api/verification/request-otp",
                           json={"application_id": 999999}, headers=headers)
    assert response.status_code == 404

    # verifying without ever requesting an OTP
    response = _verify_otp(client, headers, application_id, "123456")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_pending_otp"


# ------------------------------------------------------------------ consent

def test_consent_requires_verified_identity(client):
    headers, application_id = _register_and_apply(client)
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_consent_declined_categories_rejected_then_granted(client):
    headers, application_id = _register_and_apply(client)
    otp = _request_otp(client, headers, application_id)
    assert _verify_otp(client, headers, application_id,
                      otp["simulated_otp"]).json()["status"] == "verified"
    submit_employment(client, headers, application_id, VALID_APPLICATION)

    # declining any category blocks scoring with a clear message
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": False,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "consent_required"
    assert "telecom_activity" in body["message"]

    # missing keys count as declined too
    response = client.post("/api/consent",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 422

    granted = _grant_full_consent(client, headers, application_id)
    assert granted["status"] == "consented"
    assert len(granted["categories"]) == 4

    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["status"] == "consented"
    assert detail["consent"]["wallet_activity"] is True
    assert detail["consent"]["previous_loan_info"] is True

    # consent is recorded once per application
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consent_already_recorded"


# ---------------------------------------------------- questionnaire scoring

def test_questionnaire_min_max_and_midpoint_scores():
    positive_only = [1 if not q["reversed"] else 5 for q in QUESTIONS]
    assert score_questionnaire(positive_only) == (0.0, [])

    maximum = [5 if not q["reversed"] else 1 for q in QUESTIONS]
    assert score_questionnaire(maximum) == (100.0, [])

    # neutral answers everywhere -> exact midpoint, fully consistent
    assert score_questionnaire([3] * 12) == (50.0, [])

    # balanced wording: agreeing (or disagreeing) with everything is also
    # the midpoint — but straightlining trips every consistency pair
    for same_answer in ([1] * 12, [5] * 12):
        score, warnings = score_questionnaire(same_answer)
        assert score == 50.0
        assert len(warnings) == len(CONSISTENCY_PAIRS)


def test_questionnaire_reverse_scoring_moves_the_score():
    neutral = [3] * 12
    # question 2 is negatively worded: disagreeing (1) orients to 5
    disagree_with_negative = neutral.copy()
    disagree_with_negative[1] = 1
    score, _ = score_questionnaire(disagree_with_negative)
    assert score == 54.2  # (38 - 12) / 48 * 100

    agree_with_negative = neutral.copy()
    agree_with_negative[1] = 5
    score, _ = score_questionnaire(agree_with_negative)
    assert score == 45.8  # (34 - 12) / 48 * 100


def test_questionnaire_consistency_warnings():
    answers = [3] * 12
    # pair (1, 9): q1 positively worded, q9 negatively worded
    answers[0] = 5   # oriented 5: keeps money aside
    answers[8] = 4   # oriented 2: often runs out of money
    score, warnings = score_questionnaire(answers)
    assert any("1 and 9" in w for w in warnings)
    assert len(warnings) == 1
    # a warning never changes the score: (37 - 12) / 48 * 100
    assert score == 52.1


# ------------------------------------------------- questionnaire endpoints

def test_questions_endpoint_serves_instrument(client):
    response = client.get("/api/assessment/questions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["questions"]) == 12
    dimensions = {q["dimension"] for q in body["questions"]}
    assert dimensions == {
        "Financial Discipline", "Repayment Responsibility",
        "Spending Control", "Financial Planning"}
    assert body["scale"] == ["Strongly Disagree", "Disagree", "Neutral",
                             "Agree", "Strongly Agree"]
    assert "not a scientifically validated" in body["note"]
    # the reversed flags stay internal
    assert "reversed" not in str(body["questions"][0])


def test_questionnaire_requires_consent(client):
    headers, application_id = _register_and_apply(client)
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": [3] * 12},
                           headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_questionnaire_submit_flow(client):
    headers, application_id = _complete_through_consent(client)

    # shape and Likert-range validation
    for bad in ([3] * 11, [3] * 13, [0] + [3] * 11, [3] * 11 + [6]):
        response = client.post("/api/assessment/psychometric",
                               json={"application_id": application_id,
                                     "answers": bad},
                               headers=headers)
        assert response.status_code == 422, bad

    answers = [3] * 12
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": answers},
                           headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["psychometric_score"] == 50.0
    assert body["consistency_warnings"] == []
    assert "prototype" in body["note"].lower()

    detail = client.get(f"/api/applications/{application_id}",
                        headers=headers).json()
    assert detail["status"] == "assessed"
    assert detail["questionnaire"]["psychometric_score"] == 50.0

    # double submission
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": answers},
                           headers=headers)
    assert response.status_code == 409


def test_consistency_warning_returned_but_never_rejects(client):
    headers, application_id = _complete_through_consent(client)
    answers = [3] * 12
    answers[0] = 5
    answers[8] = 4
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": answers},
                           headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert any("1 and 9" in w for w in body["consistency_warnings"])
    assert body["psychometric_score"] == 52.1


# --------------------------------------------------------------------- meta

def test_feature_sources_endpoint(client):
    from explanation_utils import MODEL_FEATURES
    response = client.get("/api/meta/feature-sources")
    assert response.status_code == 200
    features = response.json()["features"]
    assert set(features) == set(MODEL_FEATURES)
    for entry in features.values():
        assert entry["label"] and entry["source"] and entry["description"]


def test_consent_info_endpoint(client):
    response = client.get("/api/consent/info")
    assert response.status_code == 200
    body = response.json()
    # four always-applicable categories + the bank category (Phase 2: only
    # required for applications that declared a bank account)
    assert set(body["categories"]) == {
        "wallet_activity", "telecom_activity",
        "digital_transactions", "previous_loan_info",
        "bank_account_data"}
    assert "cannot be used" in body["notice"]
