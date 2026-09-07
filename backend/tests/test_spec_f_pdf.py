"""Spec §18 F — PDF report.

The report is generated, contains the applicant's data, shows exactly the
inference score and category, and carries the required disclaimer.
"""

import io

from pypdf import PdfReader

from backend.scoring import REPORTS_DIR
from backend.tests.flow import MODERATE, full_flow, likert_answers, score


def _full_pdf_text(client, headers, application_id):
    response = client.get(f"/api/applications/{application_id}/report",
                          headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    return response.content, "\n".join(
        page.extract_text()
        for page in PdfReader(io.BytesIO(response.content)).pages
    )


# ------------------------------------------------------------ generated

def test_report_is_generated(client, offline_explanations):
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    result = score(client, headers, application_id)

    content, text = _full_pdf_text(client, headers, application_id)
    assert content[:5] == b"%PDF-"
    # a real multi-section report (no embedded chart image - raw
    # contribution numbers are hidden from applicants)
    assert len(content) > 5_000
    assert len(text.strip()) > 500
    # the persisted file matches the filename the API reported
    assert (REPORTS_DIR / result["report_filename"]).exists()


# ------------------------------------------------------- applicant data

def test_pdf_contains_the_applicant_data(client, offline_explanations):
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    score(client, headers, application_id)

    _, text = _full_pdf_text(client, headers, application_id)
    assert "PKR 65,000" in text        # declared monthly income
    assert "Self-Employed" in text     # occupation level (not encoded name)
    assert "No Previous Loan" in text  # declared loan history


# --------------------------------------------- score/category match inference

def test_pdf_score_and_category_match_the_api(client, offline_explanations):
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    result = score(client, headers, application_id)

    _, text = _full_pdf_text(client, headers, application_id)
    assert f"{result['repayment_score']:.1f}" in text
    assert result["score_category"] in text


# ------------------------------------------------------------ disclaimer

def test_pdf_carries_the_required_disclaimer(client, offline_explanations):
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    score(client, headers, application_id)

    _, text = _full_pdf_text(client, headers, application_id)
    lowered = text.lower()
    assert "not a guaranteed probability" in lowered
    assert "synthetic dataset" in lowered       # prototype disclosure
    assert "loan approval" in lowered           # not an approval decision


def test_pdf_excludes_internal_terminology(client, offline_explanations):
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    score(client, headers, application_id)

    _, text = _full_pdf_text(client, headers, application_id)
    for forbidden in ("occupation_", "existing_loan_history_", "SHAP"):
        assert forbidden not in text


# ------------------------------------------------- file-loss recovery

def test_report_is_re_rendered_after_file_loss(client, offline_explanations):
    """Deleting the PDF from disk must not lose the applicant's report."""
    headers, application_id = full_flow(client, MODERATE, likert_answers("mid"))
    result = score(client, headers, application_id)

    path = REPORTS_DIR / result["report_filename"]
    original_bytes = path.read_bytes()
    path.unlink()

    response = client.get(f"/api/applications/{application_id}/report",
                          headers=headers)
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"
    # deterministic re-render: same score content in a fresh file
    _, text = _full_pdf_text(client, headers, application_id)
    assert f"{result['repayment_score']:.1f}" in text
    # the regenerated file differs in metadata but keeps the substance
    assert len(response.content) > 5_000
    assert original_bytes  # sanity: we did read the original before deleting
