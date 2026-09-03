"""Shared test fixtures — isolated SQLite database for the API tests.

The DATABASE_URL and UPLOADS_DIR environment overrides happen before any
backend import so tests never touch the real credit_scoring.db or the real
uploads directory.
"""

import os
import shutil
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
_TEST_DB = _TEST_DIR / "_test_api.db"
_TEST_UPLOADS = _TEST_DIR / "_test_uploads"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["UPLOADS_DIR"] = str(_TEST_UPLOADS)
if _TEST_DB.exists():
    _TEST_DB.unlink()
if _TEST_UPLOADS.exists():
    shutil.rmtree(_TEST_UPLOADS)

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
    if _TEST_UPLOADS.exists():
        shutil.rmtree(_TEST_UPLOADS)


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
    from backend.tests.flow import unique_identity

    response = client.post("/api/auth/register", json=unique_identity())
    assert response.status_code == 200, response.text
    return {"X-Session-Token": response.json()["session_token"]}
