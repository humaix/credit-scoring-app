"""Shared end-to-end flow helpers for the backend test suites.

Registers a unique applicant (with password + CNIC images, as Phase 1
requires), walks the product flow and returns auth headers plus the
application id, so spec-section suites can focus on their assertions.
"""

import base64
import io
import itertools

from PIL import Image

from backend.questionnaire import QUESTIONS

TEST_PASSWORD = "Roshan123"

STRONG = {
    "age": 45, "occupation": "Business Owner", "monthly_income": 120000,
    "monthly_debt_payments": 14400,
    "existing_loan_history": "Good Repayment History",
    "requested_loan_size": 300000, "digital_purchase_frequency": 8,
    "has_bank_account": False,
}
MODERATE = {
    "age": 38, "occupation": "Self-Employed", "monthly_income": 65000,
    "monthly_debt_payments": 19500,
    "existing_loan_history": "No Previous Loan",
    "requested_loan_size": 500000, "digital_purchase_frequency": 5,
    "has_bank_account": False,
}
WEAK = {
    "age": 26, "occupation": "Daily Wage Worker", "monthly_income": 28000,
    "monthly_debt_payments": 15400,
    "existing_loan_history": "Previous Default",
    "requested_loan_size": 350000, "digital_purchase_frequency": 2,
    "has_bank_account": False,
}

# Phase 2: a complete bank-account-holder declaration (YES path)
WITH_BANK = {
    **MODERATE,
    "has_bank_account": True,
    "bank_name": "Habib Bank Limited",
    "bank_account_title": "Hina Raza",
    "bank_iban": "PK36SCBL0000001123456702",
    "wallet_provider": "JazzCash",
}

_identity_counter = itertools.count(9000)


def cnic_image_b64(width=640, height=480, brightness=120) -> str:
    """A base64 JPEG that passes the CNIC image quality checks."""
    image = Image.new("RGB", (width, height), (brightness,) * 3)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


def document_image_b64(width=640, height=480, brightness=150) -> str:
    """A base64 JPEG distinct from the CNIC images (different tone), so an
    employment document passes the duplicate screen by default."""
    return cnic_image_b64(width=width, height=height, brightness=brightness)


def unique_identity(cnic_prefix="35202") -> dict:
    """A complete, distinct registration payload per call (tests share one DB)."""
    n = next(_identity_counter)
    return {
        "full_name": "Hina Raza",
        "cnic": f"{cnic_prefix}-{n:07d}-7",
        "email": f"hina{n}@example.com",
        "mobile": "03111234567",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
        "cnic_front_image": cnic_image_b64(),
        "cnic_back_image": cnic_image_b64(),
    }


def likert_answers(orientation):
    """Likert answers producing a high / mid / low psychometric score."""
    if orientation == "high":
        return [5 if not q["reversed"] else 1 for q in QUESTIONS]   # 100.0
    if orientation == "low":
        return [2 if not q["reversed"] else 4 for q in QUESTIONS]   # 25.0
    return [3] * 12                                                 # 50.0


def full_flow(client, payload, answers):
    """register -> application -> OTP verify -> employment -> consent -> questionnaire."""
    response = client.post("/api/auth/register", json=unique_identity())
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

    submit_employment(client, headers, application_id, payload)

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


def employment_submission_for(payload) -> dict:
    """The Phase 3 employment submission matching an application payload."""
    occupation = payload.get("occupation", "Other")
    submission = {}
    if occupation == "Salaried":
        submission["employer_name"] = "Systems Ltd"
    if occupation in ("Business Owner", "Self-Employed"):
        submission["business_name"] = "Raza Traders"
    # salaried and business applicants declare their salary/income; every
    # other occupation accepts no employment fields at all
    if occupation == "Salaried" or occupation in ("Business Owner",
                                                  "Self-Employed"):
        submission["declared_income"] = payload["monthly_income"]
        # salaried applicants capture a salary slip; business applicants
        # only when they declared a bank account (statement is conditional)
        if occupation == "Salaried" or payload.get("has_bank_account"):
            submission["document_image"] = document_image_b64()
    return submission


def submit_employment(client, headers, application_id, payload) -> dict:
    """Submit the Phase 3 employment step for an application payload."""
    response = client.post("/api/employment", json={
        "application_id": application_id,
        **employment_submission_for(payload),
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def score(client, headers, application_id):
    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()
