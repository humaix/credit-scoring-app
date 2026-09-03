"""Spec §18 A — Input Validation.

Valid inputs, missing fields, invalid ranges, invalid categories and
malformed requests for every request schema in the product.
"""

import pytest

from backend.tests.flow import MODERATE, STRONG, WEAK, unique_identity


def _register(client):
    body = client.post("/api/auth/register", json=unique_identity()).json()
    return {"X-Session-Token": body["session_token"]}


# ------------------------------------------------------------ valid inputs

def test_valid_profiles_accepted(client):
    headers = _register(client)
    for payload in (STRONG, MODERATE, WEAK):
        response = client.post("/api/applications", json=payload,
                               headers=headers)
        assert response.status_code == 201, (payload, response.text)


def test_valid_boundary_values_accepted(client):
    """The exact min/max of every model range is legal input."""
    headers = _register(client)
    boundaries = [
        {**MODERATE, "age": 18, "monthly_income": 1000,
         "monthly_debt_payments": 0,  # must stay <= the boundary income
         "requested_loan_size": 10000, "digital_purchase_frequency": 0},
        {**MODERATE, "age": 65, "monthly_income": 5000000,
         "requested_loan_size": 10000000, "digital_purchase_frequency": 200},
    ]
    for payload in boundaries:
        response = client.post("/api/applications", json=payload,
                               headers=headers)
        assert response.status_code == 201, payload


def test_valid_registration_and_login(client):
    identity = unique_identity()
    response = client.post("/api/auth/register", json=identity)
    assert response.status_code == 200
    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": identity["password"]})
    assert response.status_code == 200


# ---------------------------------------------------------- missing fields

@pytest.mark.parametrize("missing", [
    "full_name", "cnic", "mobile", "email", "password",
    "confirm_password", "cnic_front_image", "cnic_back_image",
])
def test_register_missing_fields(client, missing):
    payload = {k: v for k, v in unique_identity().items() if k != missing}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert missing in fields


@pytest.mark.parametrize("missing", [
    "age", "occupation", "monthly_income", "monthly_debt_payments",
    "existing_loan_history", "requested_loan_size",
    "digital_purchase_frequency",
])
def test_application_missing_fields(client, missing):
    headers = _register(client)
    payload = {k: v for k, v in MODERATE.items() if k != missing}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert missing in fields


# ---------------------------------------------------------- invalid ranges

@pytest.mark.parametrize("field,bad_value", [
    ("age", 17), ("age", 66), ("age", "thirty-five"),
    ("monthly_income", 999), ("monthly_income", 5000001),
    ("requested_loan_size", 9999), ("requested_loan_size", 10000001),
    ("digital_purchase_frequency", -1), ("digital_purchase_frequency", 201),
    ("digital_purchase_frequency", 2.5),
])
def test_application_invalid_ranges(client, field, bad_value):
    headers = _register(client)
    payload = {**MODERATE, field: bad_value}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422, (field, bad_value)
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert field in fields


def test_debt_payments_cannot_exceed_income(client):
    headers = _register(client)
    payload = {**MODERATE, "monthly_debt_payments": MODERATE["monthly_income"] + 1}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(d["field"] == "__all__" for d in details)


def test_questionnaire_answers_out_of_range(client):
    headers, application_id = _walk_to_questionnaire(client)
    for answers in ([0] * 12, [6] * 12, [3] * 11, [3] * 13):
        response = client.post("/api/assessment/psychometric",
                               json={"application_id": application_id,
                                     "answers": answers},
                               headers=headers)
        assert response.status_code == 422, answers


# -------------------------------------------------------- invalid categories

@pytest.mark.parametrize("field,bad_value", [
    ("occupation", "Astronaut"),
    ("occupation", "business owner"),   # categories are case-sensitive
    ("existing_loan_history", "Excellent"),
    ("existing_loan_history", ""),
])
def test_application_invalid_categories(client, field, bad_value):
    headers = _register(client)
    payload = {**MODERATE, field: bad_value}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422, (field, bad_value)
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert field in fields


@pytest.mark.parametrize("bad_cnic,bad_mobile", [
    ("3520212345672", "03001234567"),        # missing dashes
    ("35202-123456-2", "03001234567"),       # 6-digit middle block
    ("35202-1234567-21", "03001234567"),     # 2-digit check digit
    ("abc02-1234567-2", "03001234567"),      # letters
    ("35202-1234567-2", "3001234567"),       # mobile missing leading 0
    ("35202-1234567-2", "04001234567"),      # mobile not 03xx
    ("35202-1234567-2", "0300123456"),       # 10 digits
])
def test_registration_invalid_identifier_formats(client, bad_cnic, bad_mobile):
    payload = {**unique_identity(), "cnic": bad_cnic, "mobile": bad_mobile}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422, (bad_cnic, bad_mobile)


# -------------------------------------------------------- malformed requests

def test_malformed_json_body(client):
    headers = _register(client)
    response = client.post(
        "/api/applications",
        content=b"{this is not json",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_wrong_types_rejected(client):
    headers = _register(client)
    payload = {**MODERATE, "age": "thirty-five", "monthly_income": "rich"}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422


def test_null_values_rejected(client):
    headers = _register(client)
    payload = {**MODERATE, "occupation": None}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422


def test_empty_body_rejected(client):
    headers = _register(client)
    response = client.post(
        "/api/applications", content=b"", headers=headers)
    assert response.status_code == 422


def test_questionnaire_non_integer_answers(client):
    headers, application_id = _walk_to_questionnaire(client)
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": ["agree"] * 12},
                           headers=headers)
    assert response.status_code == 422


# ------------------------------------------------------------------ helper

def _walk_to_questionnaire(client):
    """register + application + verification + consent (no questionnaire)."""
    body = client.post("/api/auth/register", json=unique_identity()).json()
    headers = {"X-Session-Token": body["session_token"]}
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
    return headers, application_id
