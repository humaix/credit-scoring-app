"""Shared test fixtures — isolated SQLite database for the API tests.

The DATABASE_URL environment override happens before any backend import so
tests never touch the real credit_scoring.db.
"""

import os
import secrets
from pathlib import Path

_TEST_DB = Path(__file__).resolve().parent / "_test_api.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
if _TEST_DB.exists():
    _TEST_DB.unlink()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.db import engine, init_db  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db():
    yield
    engine.dispose()  # release the SQLite file handle on Windows
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture()
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def offline_explanations(monkeypatch):
    """Deterministic fallback wording for every scoring test — never the live LLM."""
    import backend.scoring as scoring_module
    from llm_explainer import fallback_explanation

    monkeypatch.setattr(
        scoring_module, "generate_natural_language_explanation",
        fallback_explanation)


@pytest.fixture()
def session_headers(client):
    """A registered applicant's auth headers (unique CNIC per test)."""
    suffix = f"{secrets.randbelow(10_000_000):07d}"  # digits only
    payload = {
        "full_name": "Ayesha Khan",
        "cnic": f"35202-{suffix}-1",
        "mobile": "03001234567",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return {"X-Session-Token": response.json()["session_token"]}
