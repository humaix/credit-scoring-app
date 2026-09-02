"""Shared end-to-end flow helpers for the backend test suites.

Registers a unique applicant, walks the product flow and returns auth headers
plus the application id, so spec-section suites can focus on their assertions.
"""

import itertools

from backend.questionnaire import QUESTIONS

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


def unique_identity(cnic_prefix="35202"):
    """A distinct but format-valid identity per call (tests share one DB)."""
    n = next(_identity_counter)
    return {
        "full_name": "Hina Raza",
        "cnic": f"{cnic_prefix}-{n:07d}-7",
        "mobile": "03111234567",
    }


def likert_answers(orientation):
    """Likert answers producing a high / mid / low psychometric score."""
    if orientation == "high":
        return [5 if not q["reversed"] else 1 for q in QUESTIONS]   # 100.0
    if orientation == "low":
        return [2 if not q["reversed"] else 4 for q in QUESTIONS]   # 25.0
    return [3] * 12                                                 # 50.0


def full_flow(client, payload, answers):
    """register -> application -> OTP verify -> consent -> questionnaire."""
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


def score(client, headers, application_id):
    response = client.post("/api/scoring/predict",
                           json={"application_id": application_id},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()
