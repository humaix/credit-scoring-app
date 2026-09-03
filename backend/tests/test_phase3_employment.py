"""Phase 3 gate: employment / financial document verification.

Covers the new-spec Phase 3 requirements: occupation-dependent capture
(salaried -> employer + salary + salary slip; business owners / self-employed
-> business + income + bank statement only when a bank account was declared),
prototype quality checks, honest status labels ("Pending Provider
Verification" — no OCR, no provider), the blocking declared-income
consistency check (a gap beyond 20% of the application's stated monthly
income is rejected), consent gating on the completed employment step, and
financial inclusion — occupations without an applicable document still
complete the assessment.
"""

import pytest

from backend import config
from backend.db import SessionLocal
from backend.employment_docs import DOC_STATUS_LABELS
from backend.models import EmploymentVerification
from backend.tests.flow import (
    MODERATE, WEAK, WITH_BANK, cnic_image_b64, document_image_b64,
    full_flow, likert_answers, score, unique_identity,
)

SALARIED = {
    "age": 35, "occupation": "Salaried", "monthly_income": 60000,
    "monthly_debt_payments": 12000,
    "existing_loan_history": "No Previous Loan",
    "requested_loan_size": 400000, "digital_purchase_frequency": 6,
    "has_bank_account": False,
}


def _register(client, identity=None):
    response = client.post("/api/auth/register",
                           json=identity or unique_identity())
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


def _submit(client, headers, application_id, **fields):
    return client.post("/api/employment", json={
        "application_id": application_id, **fields}, headers=headers)


# ------------------------------------------------------------- salaried path

def test_salaried_salary_slip_captured_pending_verification(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd",
                       declared_income=60000,
                       document_image=document_image_b64())
    assert response.status_code == 200, response.text
    body = response.json()
    # honest prototype status: captured and quality-checked, nothing more
    assert body["status"] == "needs_review"
    assert body["status_label"] == "Pending Provider Verification"
    assert body["doc_type"] == "salary_slip"
    assert "Document-Based Prototype Verification" in body["notice"]
    assert "no OCR" in body["notice"]
    results = {c["check"]: c["result"] for c in body["checks"]}
    assert results["document_readable"] == "pass"
    assert results["duplicate_screen"] == "pass"
    assert results["income_consistency"] == "pass"

    # the document really is stored under the applicant's upload directory
    db = SessionLocal()
    try:
        record = db.query(EmploymentVerification).filter_by(
            application_id=application_id).one()
        stored = (config.UPLOADS_DIR / "employment"
                  / f"applicant_{record.application.applicant_id}"
                  / record.filename)
        assert stored.exists()
    finally:
        db.close()

    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    employment = detail["employment"]
    assert employment["employer_name"] == "Systems Ltd"
    assert employment["declared_income"] == 60000
    assert employment["occupation"] == "Salaried"
    assert employment["document_captured"] is True
    # the server-side filename never leaves the API
    assert "filename" not in employment


@pytest.mark.parametrize("missing", ["employer_name", "declared_income",
                                     "document_image"])
def test_salaried_requires_the_full_declaration(client, missing):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    fields = {"employer_name": "Systems Ltd", "declared_income": 60000,
              "document_image": document_image_b64()}
    response = _submit(client, headers, application_id,
                       **{k: v for k, v in fields.items() if k != missing})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "employment_details_required"
    assert missing in body["message"]


def test_salaried_rejects_business_fields(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=60000,
                       document_image=document_image_b64(),
                       business_name="Raza Traders")
    assert response.status_code == 422
    assert (response.json()["error"]["code"]
            == "employment_details_not_applicable")
    assert "business_name" in response.json()["error"]["message"]


# ------------------------------------------------------------- business path

def test_business_with_bank_requires_statement(client):
    headers = _register(client)
    application_id = _create(client, headers, WITH_BANK)
    _verify_otp(client, headers, application_id)

    # without the statement the submission is incomplete
    response = _submit(client, headers, application_id,
                       business_name="Raza Traders", declared_income=65000)
    assert response.status_code == 422
    assert (response.json()["error"]["code"]
            == "employment_details_required")

    # with the bank statement it becomes a pending provider verification
    response = _submit(client, headers, application_id,
                       business_name="Raza Traders", declared_income=65000,
                       document_image=document_image_b64())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["doc_type"] == "bank_statement"
    assert body["status"] == "needs_review"
    assert body["status_label"] == "Pending Provider Verification"


def test_business_without_bank_never_needs_a_statement(client):
    headers = _register(client)
    application_id = _create(client, headers, MODERATE)  # Self-Employed, NO
    _verify_otp(client, headers, application_id)

    # a statement cannot even be submitted without a bank account
    response = _submit(client, headers, application_id,
                       business_name="Raza Traders", declared_income=65000,
                       document_image=document_image_b64())
    assert response.status_code == 422
    assert (response.json()["error"]["code"]
            == "employment_details_not_applicable")
    assert "document_image" in response.json()["error"]["message"]

    # declaring the business alone is enough — no document is required
    response = _submit(client, headers, application_id,
                       business_name="Raza Traders", declared_income=65000)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["doc_type"] == "not_required"
    assert body["status"] == "not_required"
    assert "did not declare a bank account" in body["notice"]
    assert "alternative data" in body["notice"]


# ------------------------------------------------------ occupations without

@pytest.mark.parametrize("payload", [WEAK,
                                     {**MODERATE, "occupation": "Freelancer"},
                                     {**MODERATE, "occupation": "Other"}])
def test_occupations_without_document_proceed_on_alternative_data(
        client, payload):
    headers = _register(client)
    application_id = _create(client, headers, payload)
    _verify_otp(client, headers, application_id)

    # nothing is accepted — not even a document
    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd")
    assert response.status_code == 422

    # the bare submission records that no document applies
    response = _submit(client, headers, application_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["doc_type"] == "not_required"
    assert body["status"] == "not_required"
    assert body["status_label"] == "Not Required"
    assert body["notice"].startswith("No employment document is applicable")

    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["employment"]["document_captured"] is False


# -------------------------------------------------------- prototype checks

def test_income_mismatch_blocks_the_submission(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    # salary on the slip far below the application's monthly income
    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=20000,
                       document_image=document_image_b64())
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "employment_income_mismatch"
    # the error names both amounts and the allowed range
    assert "60,000" in body["message"]
    assert "20,000" in body["message"]
    assert "20%" in body["message"]
    assert "cannot proceed" in body["message"]

    # nothing was stored — the applicant can correct the amount and retry
    db = SessionLocal()
    try:
        assert db.query(EmploymentVerification).filter_by(
            application_id=application_id).count() == 0
    finally:
        db.close()

    # a consistent retry goes through
    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=55000,
                       document_image=document_image_b64())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "needs_review"
    results = {c["check"]: c["result"] for c in response.json()["checks"]}
    assert results["income_consistency"] == "pass"


def test_income_mismatch_uses_bank_statement_wording(client):
    headers = _register(client)
    application_id = _create(client, headers, WITH_BANK)
    _verify_otp(client, headers, application_id)

    # declared income far above the application's monthly income
    response = _submit(client, headers, application_id,
                       business_name="Raza Traders", declared_income=90000,
                       document_image=document_image_b64())
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "employment_income_mismatch"
    assert "bank statement" in body["message"]
    assert "65,000" in body["message"]
    assert "90,000" in body["message"]


def test_income_exactly_at_the_tolerance_is_accepted(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    # 72,000 is exactly +20% of the stated 60,000 — still consistent
    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=72000,
                       document_image=document_image_b64())
    assert response.status_code == 200, response.text
    results = {c["check"]: c["result"] for c in response.json()["checks"]}
    assert results["income_consistency"] == "pass"


def test_document_identical_to_cnic_is_rejected(client):
    identity = unique_identity()
    reused_cnic = identity["cnic_front_image"]
    headers = _register(client, identity)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=60000,
                       document_image=reused_cnic)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "employment_document"
    assert "identical to the uploaded CNIC front image" in body["message"]


@pytest.mark.parametrize("image,label", [
    (cnic_image_b64(width=100, height=80), "too small"),
    (cnic_image_b64(brightness=10), "too dark"),
    ("bm90IGFuIGltYWdl", "valid image"),
    ("!!!not-base64!!!", "decoded"),
])
def test_poor_quality_documents_rejected(client, image, label):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=60000,
                       document_image=image)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "employment_document"
    assert label in body["message"].lower()
    assert "Salary slip" in body["message"]


# ------------------------------------------------------------ flow gating

def test_consent_requires_the_employment_step(client):
    headers = _register(client)
    application_id = _create(client, headers, MODERATE)
    _verify_otp(client, headers, application_id)

    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 409
    assert (response.json()["error"]["code"]
            == "employment_verification_required")

    _submit(client, headers, application_id,
            business_name="Raza Traders", declared_income=65000)
    response = client.post("/api/consent", json={
        "application_id": application_id,
        "wallet_activity": True, "telecom_activity": True,
        "digital_transactions": True, "previous_loan_info": True,
    }, headers=headers)
    assert response.status_code == 200, response.text


def test_employment_requires_verified_identity(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)

    response = _submit(client, headers, application_id,
                       employer_name="Systems Ltd", declared_income=60000,
                       document_image=document_image_b64())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_employment_submitted_once(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)
    _verify_otp(client, headers, application_id)

    fields = {"employer_name": "Systems Ltd", "declared_income": 60000,
              "document_image": document_image_b64()}
    assert _submit(client, headers, application_id, **fields).status_code == 200
    response = _submit(client, headers, application_id, **fields)
    assert response.status_code == 409
    assert (response.json()["error"]["code"]
            == "employment_already_submitted")


def test_employment_requires_session_and_ownership(client):
    headers = _register(client)
    application_id = _create(client, headers, SALARIED)

    response = client.post("/api/employment",
                           json={"application_id": application_id})
    assert response.status_code == 401

    other = client.post("/api/auth/register", json=unique_identity()).json()
    response = _submit(client, {"X-Session-Token": other["session_token"]},
                       application_id, employer_name="Systems Ltd",
                       declared_income=60000,
                       document_image=document_image_b64())
    assert response.status_code == 404

    response = client.post(
        "/api/employment", json={"application_id": 999999},
        headers=headers)
    assert response.status_code == 404


# ------------------------------------------------- status vocabulary / flow

def test_status_vocabulary_matches_the_spec():
    # all three spec statuses exist in the vocabulary...
    assert DOC_STATUS_LABELS["data_matched"] == "Data Matched"
    assert DOC_STATUS_LABELS["could_not_verify"] == "Could Not Verify"
    # ...but the honest prototype label for a captured document is the
    # pending-provider one, and "not required" covers occupations without
    assert DOC_STATUS_LABELS["needs_review"] == "Pending Provider Verification"
    assert DOC_STATUS_LABELS["not_required"] == "Not Required"


def test_salaried_and_document_free_paths_still_score(client,
                                                      offline_explanations):
    # financial inclusion: every occupation completes the assessment
    headers, application_id = full_flow(client, WEAK, likert_answers("mid"))
    result = score(client, headers, application_id)
    assert result["status"] == "scored"
    detail = client.get(
        f"/api/applications/{application_id}", headers=headers).json()
    assert detail["employment"]["status"] == "not_required"
    assert detail["employment"]["doc_type"] == "not_required"
