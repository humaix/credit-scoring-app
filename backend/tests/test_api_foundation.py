"""Phase 2 gate: health, malformed JSON, validation errors, core flow."""

import itertools

from backend.tests.flow import cnic_image_b64

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

_identity_counter = itertools.count(1)


def _unique_identity():
    """A distinct, complete registration payload per call (shared DB)."""
    n = next(_identity_counter)
    return {
        "full_name": "Bilal Ahmed",
        "cnic": f"42201-{n:07d}-2",
        "email": f"bilal{n}@example.com",
        "mobile": "03211234567",
        "password": "Roshan123",
        "confirm_password": "Roshan123",
        "cnic_front_image": cnic_image_b64(),
        "cnic_back_image": cnic_image_b64(),
    }


def _register(client, identity=None):
    identity = identity or _unique_identity()
    response = client.post("/api/auth/register", json=identity)
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "service": "alternative-credit-scoring-api"}


def test_malformed_json_returns_structured_error(client):
    response = client.post(
        "/api/auth/register",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert "message" in body and isinstance(body["details"], list)


def test_register_field_validation(client):
    cases = [
        {"full_name": "B", "cnic": "42201-1234567-2", "email": "b@example.com",
         "mobile": "03211234567", "password": "Roshan123",
         "confirm_password": "Roshan123",
         "cnic_front_image": cnic_image_b64(), "cnic_back_image": cnic_image_b64()},
        {**_unique_identity(), "cnic": "4220112345672"},
        {**_unique_identity(), "mobile": "3211234567"},
        {**_unique_identity(), "email": "not-an-email"},
        {**_unique_identity(), "password": "short1"},
    ]
    for payload in cases:
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "validation_error"
    # details point at the offending field
    response = client.post(
        "/api/auth/register", json={**_unique_identity(), "cnic": "bad"})
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "cnic" in fields


def test_register_duplicate_cnic_rejected(client):
    identity = _unique_identity()
    _register(client, identity)
    response = client.post("/api/auth/register", json=identity)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_registered"


def test_register_masks_identifiers(client):
    identity = _unique_identity()
    body = _register(client, identity)
    assert body["applicant"]["cnic_masked"] == "42201-*******-2"
    assert body["applicant"]["mobile_masked"] == "0321****567"
    # the raw identifiers must never appear in the response
    assert identity["cnic"] not in str(body)
    assert identity["mobile"] not in str(body)


def test_login(client):
    identity = _unique_identity()
    _register(client, identity)
    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": identity["password"]})
    assert response.status_code == 200
    assert response.json()["session_token"]
    # wrong password -> rejected
    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": "WrongPass9"})
    assert response.status_code == 401
    # unknown CNIC -> rejected with the identical message (no enumeration)
    response = client.post("/api/auth/login", json={
        "cnic": "11111-1111111-1", "password": "Whatever1"})
    assert response.status_code == 401
    assert (response.json()["error"]["message"]
            == "CNIC or password is incorrect")


def test_create_application_requires_session(client):
    response = client.post("/api/applications", json=VALID_APPLICATION)
    assert response.status_code == 401
    response = client.post(
        "/api/applications", json=VALID_APPLICATION,
        headers={"X-Session-Token": "not-a-real-token"})
    assert response.status_code == 401


def test_create_and_fetch_application(client):
    body = _register(client)
    headers = {"X-Session-Token": body["session_token"]}

    response = client.post("/api/applications", json=VALID_APPLICATION,
                           headers=headers)
    assert response.status_code == 201, response.text
    application_id = response.json()["application_id"]
    assert response.json()["status"] == "created"

    response = client.get(f"/api/applications/{application_id}", headers=headers)
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == application_id
    assert detail["status"] == "created"
    assert detail["monthly_income"] == 60000
    assert detail["applicant"]["cnic_masked"] == "42201-*******-2"
    assert detail["verification"] is None  # filled in phase 3

    # listing returns the application
    response = client.get("/api/applications", headers=headers)
    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [application_id]

    # unknown id -> 404
    response = client.get("/api/applications/99999", headers=headers)
    assert response.status_code == 404


def test_application_ownership_isolated(client):
    first = _register(client)
    headers = {"X-Session-Token": first["session_token"]}
    application_id = client.post(
        "/api/applications", json=VALID_APPLICATION, headers=headers
    ).json()["application_id"]

    other = _register(client, {
        "full_name": "Sana Malik",
        "cnic": "35201-7654321-9",
        "email": "sana.malik@example.com",
        "mobile": "03331234567",
        "password": "Roshan123",
        "confirm_password": "Roshan123",
        "cnic_front_image": cnic_image_b64(),
        "cnic_back_image": cnic_image_b64(),
    })
    other_headers = {"X-Session-Token": other["session_token"]}

    # the other applicant cannot read or see the first applicant's application
    response = client.get(f"/api/applications/{application_id}",
                          headers=other_headers)
    assert response.status_code == 404
    response = client.get("/api/applications", headers=other_headers)
    assert response.json() == []


def test_application_validation_errors(client):
    body = _register(client)
    headers = {"X-Session-Token": body["session_token"]}

    cases = [
        ({**VALID_APPLICATION, "occupation": "Astronaut"}, "occupation"),
        ({**VALID_APPLICATION, "existing_loan_history": "Excellent"}, "existing_loan_history"),
        ({**VALID_APPLICATION, "age": 17}, "age"),
        ({**VALID_APPLICATION, "age": 66}, "age"),
        ({**VALID_APPLICATION, "monthly_income": 500}, "monthly_income"),
        ({**VALID_APPLICATION, "requested_loan_size": 5000}, "requested_loan_size"),
        ({**VALID_APPLICATION, "digital_purchase_frequency": 500}, "digital_purchase_frequency"),
        ({**VALID_APPLICATION, "monthly_debt_payments": 999999}, "__all__"),
    ]
    for payload, expected_field in cases:
        response = client.post("/api/applications", json=payload, headers=headers)
        assert response.status_code == 422, payload
        details = response.json()["error"]["details"]
        assert any(d["field"] == expected_field for d in details), payload

    # missing field
    payload = {k: v for k, v in VALID_APPLICATION.items() if k != "age"}
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 422


def test_error_responses_never_leak_internals(client, session_headers):
    # authenticated call with a non-integer path param -> structured 422
    response = client.get("/api/applications/abc", headers=session_headers)
    assert response.status_code == 422
    text = response.text
    assert "Traceback" not in text
    assert ".py" not in text  # no file paths leaked
