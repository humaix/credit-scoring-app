"""Scoring service: built features -> saved pipeline -> SHAP -> LLM -> PDF.

Reuses the existing explainability engine exactly as the CLI and Streamlit
paths do — validate_applicant_data (Layer 5 model-input gate),
assess_applicant (prediction + TreeSHAP with the additivity check),
generate_natural_language_explanation (LLM wording, deterministic fallback),
render_report (ReportLab PDF). The saved pipeline is loaded once (cached in
shap_explainer) and is never retrained or re-saved.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from explanation_utils import (
    FEATURE_LABELS, MODEL_FEATURES, format_feature_value, validate_applicant_data,
)
from llm_explainer import generate_natural_language_explanation
from report_generator import render_report
from shap_explainer import assess_applicant

from . import config
from .errors import ApiError
from .feature_builder import PROVIDER_SIMULATION_NOTE, build_features
from .models import Application, AssessmentResult, ReportFile

REPORTS_DIR = Path(config.PROJECT_ROOT) / "generated_reports"

_STEP_ORDER = "created -> verified -> consented -> assessed -> scored"

SCORE_DISCLAIMER = (
    "This score is a model-estimated repayment assessment and is not a "
    "guaranteed probability of repayment or an automatic loan approval decision."
)


def _pdf_path_for(application_id: int) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"repayment_assessment_app{application_id}_{stamp}.pdf"
    counter = 1
    while path.exists():
        counter += 1
        path = REPORTS_DIR / (
            f"repayment_assessment_app{application_id}_{stamp}_{counter}.pdf")
    return path


def _rebuild_assessment(row: AssessmentResult) -> dict:
    """Rebuild the render_report input from persisted values (file recovery)."""
    features = row.applicant_features
    return {
        "repayment_score": row.repayment_score,
        "raw_score": row.raw_score,
        "score_category": row.score_category,
        "applicant_features": [
            {"feature": FEATURE_LABELS[name],
             "value": format_feature_value(name, features[name])}
            for name in MODEL_FEATURES
        ],
        "positive_contributors": row.positive_contributors,
        "negative_contributors": row.negative_contributors,
        "all_contributions": row.all_contributions,
        "base_value": row.base_value,
    }


def latest_report_path(db: Session, application: Application) -> Path:
    """Path to the application's PDF, re-rendering it if the file was lost."""
    report = (
        db.query(ReportFile)
        .filter(ReportFile.application_id == application.id)
        .order_by(ReportFile.created_at.desc(), ReportFile.id.desc())
        .first()
    )
    if report is not None:
        path = REPORTS_DIR / report.filename
        if path.exists():
            return path

    # assessment exists but the file is gone -> deterministic re-render
    row = application.assessment
    pdf_path = _pdf_path_for(application.id)
    render_report(_rebuild_assessment(row), row.explanation, pdf_path)
    db.add(ReportFile(application_id=application.id, assessment_id=row.id,
                      filename=pdf_path.name))
    db.commit()
    return pdf_path


def run_scoring(db: Session, application: Application) -> dict:
    """Score one assessed application and persist every artefact."""
    existing = (
        db.query(AssessmentResult)
        .filter(AssessmentResult.application_id == application.id)
        .first()
    )
    if existing is not None:
        raise ApiError(409, "already_scored",
                       "This application has already been scored")

    if application.status != "assessed":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: {_STEP_ORDER}")

    features, warnings = build_features(application)

    # Layer 5: the exact feature vector the saved pipeline expects
    try:
        applicant = validate_applicant_data(features)
    except ValueError as exc:
        raise ApiError(422, "feature_validation", str(exc))

    assessment = assess_applicant(applicant)
    explanation = generate_natural_language_explanation(assessment)

    pdf_path = _pdf_path_for(application.id)
    render_report(assessment, explanation, pdf_path)

    row = AssessmentResult(
        application_id=application.id,
        repayment_score=assessment["repayment_score"],
        raw_score=assessment["raw_score"],
        score_category=assessment["score_category"],
        base_value=assessment["base_value"],
        positive_contributors=assessment["positive_contributors"],
        negative_contributors=assessment["negative_contributors"],
        all_contributions=assessment["all_contributions"],
        applicant_features=applicant,
        explanation=explanation,
        explanation_source=explanation["source"],
    )
    db.add(row)
    db.flush()  # row.id is needed for the report record
    db.add(ReportFile(application_id=application.id, assessment_id=row.id,
                      filename=pdf_path.name))
    application.status = "scored"
    db.commit()

    return {
        "application_id": application.id,
        "status": "scored",
        "repayment_score": assessment["repayment_score"],
        "raw_score": assessment["raw_score"],
        "score_category": assessment["score_category"],
        "base_value": assessment["base_value"],
        "positive_contributors": assessment["positive_contributors"],
        "negative_contributors": assessment["negative_contributors"],
        "all_contributions": assessment["all_contributions"],
        "explanation": explanation,
        "explanation_source": explanation["source"],
        "consistency_warnings": warnings,
        "provider_note": PROVIDER_SIMULATION_NOTE,
        "disclaimer": SCORE_DISCLAIMER,
        "report_filename": pdf_path.name,
    }
