"""Phase 1 gate: account creation, password auth, CNIC capture, reset flow.

Covers the new-spec Phase 1 requirements: six-field registration with hashed
passwords, CNIC front/back image capture with quality validation, CNIC +
password login (no enumeration leakage), logout, and the forgot/reset
password flow (expiring, single-use, hashed tokens).
"""

import base64
import hashlib
from datetime import datetime, timedelta

import pytest

from backend import config
from backend.db import SessionLocal
from backend.models import PasswordResetToken
from backend.tests.flow import TEST_PASSWORD, cnic_image_b64, unique_identity


def _register(client, identity=None):
    identity = identity or unique_identity()
    response = client.post("/api/auth/register", json=identity)
    assert response.status_code == 200, response.text
    return identity, response.json()


# --------------------------------------------------------- registration

def test_register_returns_prototype_verified_status(client):
    identity, body = _register(client)
    assert body["applicant"]["cnic_status"] == "prototype_verified"
    assert "no nadra" in body["cnic_notice"].lower()
    assert "no ocr" in body["cnic_notice"].lower()
    # identifiers are masked; raw values never appear in the response
    assert body["applicant"]["cnic_masked"].startswith("35202-")
    assert body["applicant"]["email_masked"].endswith("@example.com")
    assert "@" in body["applicant"]["email_masked"]
    assert identity["email"] not in str(body)
    assert identity["password"] not in str(body)


def test_register_passwords_never_stored_in_plain_text(client):
    from backend.models import Applicant

    identity, _ = _register(client)
    db = SessionLocal()
    try:
        row = db.query(Applicant).filter(
            Applicant.cnic == identity["cnic"]).first()
        assert row.password_hash is not None
        assert row.password_hash != identity["password"]
        assert row.password_hash.startswith("$2")  # bcrypt format
    finally:
        db.close()


@pytest.mark.parametrize("password", [
    "short1",           # too short
    "nodigitshere",     # no digit
    "12345678",         # no letter
])
def test_register_rejects_weak_passwords(client, password):
    payload = {**unique_identity(), "password": password,
               "confirm_password": password}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_register_rejects_mismatched_confirm(client):
    payload = {**unique_identity(), "confirm_password": "Different1"}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_register_rejects_duplicate_email(client):
    identity, _ = _register(client)
    payload = {**unique_identity(), "email": identity["email"]}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


# ------------------------------------------------------ CNIC image checks

@pytest.mark.parametrize("side", ["cnic_front_image", "cnic_back_image"])
def test_register_requires_both_cnic_images(client, side):
    payload = {k: v for k, v in unique_identity().items() if k != side}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_register_rejects_corrupt_image(client):
    payload = {**unique_identity(),
               "cnic_front_image": base64.b64encode(
                   b"this is definitely not an image file at all").decode()}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cnic_image"
    assert "front" in response.json()["error"]["message"]


def test_register_rejects_undersized_image(client):
    payload = {**unique_identity(),
               "cnic_back_image": cnic_image_b64(width=100, height=80)}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert "back" in response.json()["error"]["message"]


def test_register_rejects_dark_image(client):
    payload = {**unique_identity(),
               "cnic_front_image": cnic_image_b64(brightness=10)}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert "dark" in response.json()["error"]["message"]


def test_register_rejects_oversized_image(client):
    payload = {**unique_identity(),
               "cnic_front_image": base64.b64encode(b"x" * (9 * 1024 * 1024)).decode()}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_cnic_images_stored_on_disk(client):
    _, body = _register(client)
    applicant_id = body["applicant"]["id"]
    directory = config.UPLOADS_DIR / "cnic" / f"applicant_{applicant_id}"
    files = sorted(p.name for p in directory.iterdir())
    assert len(files) == 2
    assert any(f.startswith("front_") for f in files)
    assert any(f.startswith("back_") for f in files)


def test_cnic_images_accepted_with_data_url_prefix(client):
    payload = {**unique_identity()}
    payload["cnic_front_image"] = (
        "data:image/jpeg;base64," + payload["cnic_front_image"])
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text


# ------------------------------------------------------------------ login

def test_login_wrong_password_and_unknown_cnic_indistinguishable(client):
    identity, _ = _register(client)
    wrong = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": "WrongPass9"})
    unknown = client.post("/api/auth/login", json={
        "cnic": "99999-9999999-9", "password": "WrongPass9"})
    assert wrong.status_code == unknown.status_code == 401
    assert (wrong.json()["error"]["message"]
            == unknown.json()["error"]["message"])


def test_login_returns_applications(client):
    identity, body = _register(client)
    headers = {"X-Session-Token": body["session_token"]}
    application_id = client.post(
        "/api/applications", json={
            "age": 35, "occupation": "Salaried", "monthly_income": 60000,
            "monthly_debt_payments": 18000,
            "existing_loan_history": "No Previous Loan",
            "requested_loan_size": 400000, "digital_purchase_frequency": 6,
        }, headers=headers).json()["application_id"]

    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": identity["password"]})
    assert response.status_code == 200
    assert [a["id"] for a in response.json()["applications"]] == [application_id]


# ----------------------------------------------------------------- logout

def test_logout_invalidates_token(client):
    identity, body = _register(client)
    headers = {"X-Session-Token": body["session_token"]}
    assert client.get("/api/applications", headers=headers).status_code == 200

    response = client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "logged_out"

    # the old token no longer works
    assert client.get("/api/applications", headers=headers).status_code == 401

    # logging back in issues a fresh working token
    response = client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": identity["password"]})
    assert response.status_code == 200
    fresh = {"X-Session-Token": response.json()["session_token"]}
    assert client.get("/api/applications", headers=fresh).status_code == 200


# --------------------------------------------------- forgot / reset password

def _request_reset(client, identity):
    response = client.post("/api/auth/forgot-password",
                           json={"cnic": identity["cnic"]})
    assert response.status_code == 200, response.text
    return response.json()


def _token_from_dev_url(dev_url):
    return dev_url.split("token=")[1]


def test_forgot_password_unknown_cnic_gets_generic_response(client):
    response = client.post("/api/auth/forgot-password",
                           json={"cnic": "99999-9999999-9"})
    assert response.status_code == 200
    body = response.json()
    assert "If an account exists" in body["message"]
    assert body.get("dev_reset_url") is None  # no account -> no link


def test_reset_flow_via_dev_link(client):
    identity, _ = _register(client)
    forgot = _request_reset(client, identity)
    assert forgot["dev_reset_url"] is not None  # dev mode default
    assert "Development mode" in forgot["dev_notice"]
    token = _token_from_dev_url(forgot["dev_reset_url"])

    # weak new password and mismatch are rejected
    for payload in ({"token": token, "new_password": "weak",
                     "confirm_password": "weak"},
                    {"token": token, "new_password": "NewRoshan456",
                     "confirm_password": "Different9"}):
        response = client.post("/api/auth/reset-password", json=payload)
        assert response.status_code == 422, response.text

    response = client.post("/api/auth/reset-password", json={
        "token": token, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 200, response.text

    # old password stopped working, new one works
    assert client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": identity["password"]}).status_code == 401
    assert client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": "NewRoshan456"}).status_code == 200

    # the token is single-use
    response = client.post("/api/auth/reset-password", json={
        "token": token, "new_password": "Again789x",
        "confirm_password": "Again789x"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired"


def test_reset_token_expires(client):
    identity, _ = _register(client)
    forgot = _request_reset(client, identity)
    token = _token_from_dev_url(forgot["dev_reset_url"])

    # age the token past its TTL directly in the database
    db = SessionLocal()
    try:
        record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash
            == hashlib.sha256(token.encode()).hexdigest()
        ).first()
        assert record is not None
        record.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    response = client.post("/api/auth/reset-password", json={
        "token": token, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired"


def test_reset_invalid_token_rejected(client):
    response = client.post("/api/auth/reset-password", json={
        "token": "x" * 40, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 400


def test_forgot_password_production_mode_hides_link(client, monkeypatch):
    """With SMTP configured the link is emailed, never returned in the API."""
    from backend import mailer as mailer_module
    from backend import routers as _  # noqa: F401  (import package graph)

    sent = []

    def fake_send(to_email, reset_url):
        sent.append((to_email, reset_url))
        return True

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mailer_module, "send_reset_email", fake_send)

    identity, _ = _register(client)
    body = _request_reset(client, identity)

    assert body.get("dev_reset_url") is None  # never leaked in the response
    assert body["message"].startswith("If an account exists")
    assert len(sent) == 1  # the email carried the link
    assert sent[0][0] == identity["email"]
    assert "/reset-password?token=" in sent[0][1]

    # the emailed link still resets the password
    token = _token_from_dev_url(sent[0][1])
    response = client.post("/api/auth/reset-password", json={
        "token": token, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 200
    assert client.post("/api/auth/login", json={
        "cnic": identity["cnic"], "password": "NewRoshan456"}).status_code == 200


def test_forgot_password_new_request_invalidates_previous_token(client):
    identity, _ = _register(client)
    first = _token_from_dev_url(_request_reset(client, identity)["dev_reset_url"])
    second = _token_from_dev_url(_request_reset(client, identity)["dev_reset_url"])

    # the older token is gone; only the newest one works
    response = client.post("/api/auth/reset-password", json={
        "token": first, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 400
    response = client.post("/api/auth/reset-password", json={
        "token": second, "new_password": "NewRoshan456",
        "confirm_password": "NewRoshan456"})
    assert response.status_code == 200
