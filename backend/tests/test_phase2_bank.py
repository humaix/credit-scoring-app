"""Phase 2 gate: bank-account question and conditional flow.

Covers the new-spec Phase 2 requirements: the "Do you have a bank account?"
question stored with the application, bank details required only on the YES
path, conditional consent categories (bank data consent never required for
applicants without a bank account), and financial inclusion — a NO applicant
still completes the full assessment.
"""

import pytest

from backend.db import SessionLocal
from backend.models import Application
from backend.tests.flow import (
    MODERATE, WEAK, WITH_BANK, full_flow, likert_answers, score,
    submit_employment, unique_identity,
)


def _register(client):
    response = client.post("/api/auth/register", json=unique_identity())
    assert response.status_code == 200, response.text
    return {"X-Session-Token": response.json()["session_token"]}


def _create(client, headers, payload):
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["application_id"]


def _verify_otp(client, headers, application_id):
    otp = client.post(
        "/api/verification/request-otp",
        json={"application_id": application_id}, headers=headers).json()
    response = client.post(
        "/api/verification/verify-otp",
        json={"application_id": application_id, "code": otp["simulated_otp"]},
        headers=headers)
    assert response.json()["status"] == "verified"


# ------------------------------------------------- application declaration

def test_yes_application_stores_bank_details_and_masks_iban(client):
    headers = _register(client)
    application_id = _create(client, headers, WITH_BANK)

    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["has_bank_account"] is True
    assert detail["bank_name"] == WITH_BANK["bank_name"]
    assert detail["bank_account_title"] == WITH_BANK["bank_account_title"]
    assert detail["wallet_provider"] == "JazzCash"
    masked = detail["bank_iban_masked"]
    assert masked.startswith("PK36") and masked.endswith("6702")
    assert "*" in masked
    # the raw IBAN/account number never leaves the API
    assert WITH_BANK["bank_iban"] not in str(detail)


@pytest.mark.parametrize("missing", ["bank_name", "bank_account_title",
                                     "bank_iban"])
def test_yes_requires_the_bank_details(client, missing):
    headers = _register(client)
    payload = {**WITH_BANK, missing: None}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422
    assert "bank" in str(response.json()["error"]).lower()


def test_no_application_rejects_bank_details(client):
    headers = _register(client)
    payload = {**MODERATE, "bank_name": "Habib Bank Limited"}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422
    assert "has_bank_account" in str(response.json()["error"])


def test_no_application_stores_no_bank_fields(client):
    headers = _register(client)
    application_id = _create(client, headers, MODERATE)
    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["has_bank_account"] is False
    assert detail["bank_name"] is None
    assert detail["bank_iban_masked"] is None


@pytest.mark.parametrize("bad_iban", [
    "PK36SC",                        # too short for IBAN or account number
    "PK36SCBL0000001123456702LONG",  # 28 characters — too long either way
    "PK36-SCBL-0000001123456702",    # dashes are not part of an IBAN
    "PK36SCBL0000!12234",            # special characters rejected
])
def test_invalid_iban_rejected(client, bad_iban):
    headers = _register(client)
    payload = {**WITH_BANK, "bank_iban": bad_iban}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422, bad_iban


def test_iban_is_normalized_before_storage(client):
    headers = _register(client)
    payload = {**WITH_BANK,
               "bank_iban": "pk36 scbl 0000 0011 2345 6702"}
    application_id = _create(client, headers, payload)

    db = SessionLocal()
    try:
        row = db.get(Application, application_id)
        assert row.bank_iban == "PK36SCBL0000001123456702"
    finally:
        db.close()


def test_plain_account_number_accepted(client):
    headers = _register(client)
    payload = {**WITH_BANK, "bank_iban": "00112233445566"}
    application_id = _create(client, headers, payload)
    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["bank_iban_masked"].endswith("5566")
    assert "*" in detail["bank_iban_masked"]


def test_wallet_provider_validated(client):
    headers = _register(client)
    response = client.post(
        "/api/applications",
        json={**WITH_BANK, "wallet_provider": "PayPal"}, headers=headers)
    assert response.status_code == 422


def test_wallet_provider_available_without_bank_account(client):
    # wallet info is not a bank field — the alternative-data path is
    # wallet-first, so a NO applicant may still declare their wallet
    headers = _register(client)
    payload = {**WEAK, "wallet_provider": "Easypaisa"}
    application_id = _create(client, headers, payload)
    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["has_bank_account"] is False
    assert detail["wallet_provider"] == "Easypaisa"


# ------------------------------------------------------- conditional consent

def test_consent_info_lists_bank_category(client):
    info = client.get("/api/consent/info").json()
    assert "bank_account_data" in info["categories"]
    assert "prototype" in info["categories"]["bank_account_data"].lower()


def test_yes_consent_requires_bank_category(client):
    headers = _register(client)
    application_id = _create(client, headers, WITH_BANK)
    _verify_otp(client, headers, application_id)
    submit_employment(client, headers, application_id, WITH_BANK)

    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
        "bank_account_data": False,
    }, headers=headers)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "consent_required"
    assert "bank_account_data" in body["message"]

    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
        "bank_account_data": True,
    }, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "bank_account_data" in body["categories"]
    assert "five" in body["notice"]

    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["consent"]["bank_account_data"] is True


def test_no_consent_never_requires_bank_category(client):
    headers = _register(client)
    application_id = _create(client, headers, MODERATE)
    _verify_otp(client, headers, application_id)
    submit_employment(client, headers, application_id, MODERATE)

    # the bank category is not applicable: granting the four alternative-data
    # categories succeeds even though bank_account_data was never sent
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "bank_account_data" not in body["categories"]
    assert "four" in body["notice"]

    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["consent"]["bank_account_data"] is False


# ---------------------------------------------------- financial inclusion

def test_no_bank_account_still_scores(client, offline_explanations):
    """Having no bank account must not block the credit assessment."""
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    result = score(client, headers, application_id)
    assert result["status"] == "scored"
    assert result["repayment_score"] is not None


def test_bank_account_full_flow_scores(client, offline_explanations):
    headers = _register(client)
    application_id = _create(client, headers, WITH_BANK)
    _verify_otp(client, headers, application_id)
    submit_employment(client, headers, application_id, WITH_BANK)

    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
        "bank_account_data": True,
    }, headers=headers)
    assert response.status_code == 200, response.text

    response = client.post("/api/assessment/psychometric", json={
        "application_id": application_id,
        "answers": likert_answers("mid"),
    }, headers=headers)
    assert response.status_code == 200, response.text

    result = score(client, headers, application_id)
    assert result["status"] == "scored"
    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["has_bank_account"] is True
    assert detail["consent"]["bank_account_data"] is True
