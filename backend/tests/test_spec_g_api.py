"""Spec §18 G — API layer.

Successful requests across every endpoint, validation errors on the step
endpoints, malformed JSON on authenticated routes, and service failures or
missing dependencies answered with sanitized structured errors — never a
stack trace, never an internal path.
"""

from pathlib import Path

from fastapi.testclient import TestClient

import backend.routers.scoring as scoring_router
from backend.main import app
from backend.tests.flow import (
    MODERATE, full_flow, likert_answers, score, unique_identity,
)


# ------------------------------------------------------ successful requests

def test_public_endpoints_succeed(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # feature-source transparency (spec §8)
    features = client.get("/api/meta/feature-sources").json()["features"]
    assert len(features) == 10
    assert all(
        {"label", "source", "description"} <= set(f) for f in features.values()
    )

    questions = client.get("/api/assessment/questions").json()
    assert len(questions["questions"]) == 12
    assert len(questions["scale"]) == 5
    # the reversed-scored flag stays internal
    assert "reversed" not in questions["questions"][0]

    info = client.get("/api/consent/info").json()
    assert len(info["categories"]) == 4
    assert "simulated" in str(info).lower()  # mock integrations labelled


def test_login_returns_session_and_existing_applications(client):
    identity = unique_identity()
    registered = client.post("/api/auth/register", json=identity).json()
    headers = {"X-Session-Token": registered["session_token"]}
    application_id = client.post(
        "/api/applications", json=MODERATE, headers=headers
    ).json()["application_id"]

    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "mobile": identity["mobile"]})
    assert response.status_code == 200
    body = response.json()
    assert body["session_token"]
    assert [a["id"] for a in body["applications"]] == [application_id]


def test_step_status_transitions_visible_in_detail(client, offline_explanations):
    registered = client.post("/api/auth/register", json=unique_identity()).json()
    headers = {"X-Session-Token": registered["session_token"]}
    application_id = client.post(
        "/api/applications", json=MODERATE, headers=headers
    ).json()["application_id"]

    def _status():
        return client.get(
            f"/api/applications/{application_id}", headers=headers
        ).json()["status"]

    assert _status() == "created"

    otp = client.post("/api/verification/request-otp",
                      json={"application_id": application_id},
                      headers=headers).json()
    assert otp["status"] == "pending"
    assert otp["simulated_otp"]  # DEV_RETURN_OTP demo mode

    verified = client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": otp["simulated_otp"]},
        headers=headers).json()
    assert verified["status"] == "verified"
    assert _status() == "verified"

    consent = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers).json()
    assert consent["status"] == "consented"
    assert _status() == "consented"

    assessment = client.post(
        "/api/assessment/psychometric",
        json={"application_id": application_id, "answers": likert_answers("mid")},
        headers=headers).json()
    assert assessment["psychometric_score"] == 50.0
    assert _status() == "assessed"

    result = score(client, headers, application_id)
    assert result["status"] == "scored"
    assert _status() == "scored"

    report = client.get(f"/api/applications/{application_id}/report",
                        headers=headers)
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content[:5] == b"%PDF-"


# -------------------------------------------------------- validation errors

def test_step_endpoints_reject_invalid_payloads(client, session_headers):
    # OTP code length must be 4-8 characters
    response = client.post("/api/verification/verify-otp",
                           json={"application_id": 1, "code": "12"},
                           headers=session_headers)
    assert response.status_code == 422
    response = client.post("/api/verification/verify-otp",
                           json={"application_id": 1, "code": "123456789"},
                           headers=session_headers)
    assert response.status_code == 422

    # consent flags must be booleans
    response = client.post("/api/consent",
                           json={"application_id": 1,
                                 "wallet_activity": "maybe"},
                           headers=session_headers)
    assert response.status_code == 422

    # questionnaire: exactly twelve answers, each on the 1-5 Likert scale
    for answers in ([3] * 11, [3] * 13, [6] * 12):
        response = client.post("/api/assessment/psychometric",
                               json={"application_id": 1, "answers": answers},
                               headers=session_headers)
        assert response.status_code == 422, answers

    # step references: shape-validated first, ownership-checked second
    for payload in ({}, {"application_id": "abc"}):
        response = client.post("/api/scoring/predict", json=payload,
                               headers=session_headers)
        assert response.status_code == 422, payload
    response = client.post("/api/scoring/predict",
                           json={"application_id": 999999},
                           headers=session_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_step_endpoints_require_authentication(client):
    protected_posts = [
        ("/api/applications", MODERATE),
        ("/api/verification/request-otp", {"application_id": 1}),
        ("/api/verification/verify-otp",
         {"application_id": 1, "code": "123456"}),
        ("/api/consent", {"application_id": 1}),
        ("/api/assessment/psychometric",
         {"application_id": 1, "answers": [3] * 12}),
        ("/api/scoring/predict", {"application_id": 1}),
    ]
    for url, payload in protected_posts:
        response = client.post(url, json=payload)
        assert response.status_code == 401, url
        assert response.json()["error"]["code"] == "unauthorized"

    # a forged token is rejected exactly like a missing one
    response = client.post("/api/applications", json=MODERATE,
                           headers={"X-Session-Token": "forged"})
    assert response.status_code == 401

    for url in ("/api/applications", "/api/applications/1",
                "/api/applications/1/report"):
        assert client.get(url).status_code == 401, url


# ----------------------------------------------------------- malformed JSON

def test_malformed_json_on_authenticated_endpoints(client, session_headers):
    endpoints = [
        "/api/applications",
        "/api/verification/request-otp",
        "/api/verification/verify-otp",
        "/api/consent",
        "/api/assessment/psychometric",
        "/api/scoring/predict",
    ]
    for url in endpoints:
        response = client.post(
            url, content=b"{not valid json",
            headers={**session_headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 422, url
        body = response.json()["error"]
        assert body["code"] == "validation_error"
        assert isinstance(body["details"], list)


# ------------------------------------------ service failures / missing deps

def test_service_failure_returns_sanitized_500(monkeypatch):
    """An unexpected internal crash answers with a structured 500 that leaks
    neither the exception message nor any file path."""
    def _boom(db, application):
        raise RuntimeError("simulated scoring service outage")

    monkeypatch.setattr(scoring_router, "run_scoring", _boom)

    with TestClient(app, raise_server_exceptions=False) as client:
        headers, application_id = full_flow(client, MODERATE,
                                            likert_answers("mid"))
        response = client.post("/api/scoring/predict",
                               json={"application_id": application_id},
                               headers=headers)

    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_error"
    assert body["message"] == "An unexpected error occurred"
    assert "simulated scoring service outage" not in response.text
    assert "Traceback" not in response.text
    assert ".py" not in response.text


def test_missing_model_dependency_returns_sanitized_500(monkeypatch):
    """A missing model file (unavailable dependency) fails closed with the
    same sanitized 500 — no path, no traceback."""
    import shap_explainer

    monkeypatch.setattr(shap_explainer, "_pipeline", None)
    monkeypatch.setattr(
        shap_explainer, "MODEL_PATH",
        Path(shap_explainer.MODEL_PATH).parent / "missing_model_dependency.pkl")

    with TestClient(app, raise_server_exceptions=False) as client:
        headers, application_id = full_flow(client, MODERATE,
                                            likert_answers("mid"))
        response = client.post("/api/scoring/predict",
                               json={"application_id": application_id},
                               headers=headers)

    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_error"
    assert "missing_model_dependency" not in response.text
    assert "Traceback" not in response.text
    assert ".py" not in response.text
