"""Entry point: applicant data -> score -> SHAP -> explanation -> PDF report.

Orchestrates the layers without touching their internals:

    validate -> saved XGBoost pipeline -> score
             -> SHAP -> structured contributions
             -> LLM (wording only, fallback templates on failure)
             -> ReportLab PDF
"""

import argparse
import json
from pathlib import Path

from explanation_utils import REPORTS_DIR, SAMPLE_APPLICANTS, validate_applicant_data
from llm_explainer import generate_natural_language_explanation
from report_generator import render_report, unique_report_path
from shap_explainer import assess_applicant


def generate_repayment_report(applicant_data, output_dir=None, return_details=False):
    """Generate an Applicant Repayment Assessment PDF for one application.

    Steps: validate input, score with the saved pipeline, compute SHAP
    contributions, write the explanation (LLM with template fallback), render
    the PDF. The saved model is loaded read-only and never retrained.

    Returns the PDF path, or a details dict when return_details=True.
    """
    applicant = validate_applicant_data(applicant_data)
    assessment = assess_applicant(applicant)
    explanation = generate_natural_language_explanation(assessment)

    output_dir = Path(output_dir) if output_dir else REPORTS_DIR
    pdf_path = unique_report_path(output_dir)
    render_report(assessment, explanation, pdf_path)

    if return_details:
        return {"pdf_path": pdf_path, "assessment": assessment, "explanation": explanation}
    return pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate an applicant repayment assessment PDF report.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true",
                       help="generate reports for the three sample applicants")
    group.add_argument("--input", metavar="JSON_FILE",
                       help="path to a JSON file with the applicant's feature values")
    args = parser.parse_args()

    if args.demo:
        applicants = SAMPLE_APPLICANTS
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        applicants = [{"label": Path(args.input).stem, "data": payload}]

    for sample in applicants:
        result = generate_repayment_report(sample["data"], return_details=True)
        assessment = result["assessment"]
        print(
            f"{sample['label']:<18} "
            f"score {assessment['repayment_score']:.1f}/100 "
            f"({assessment['score_category']})\n"
            f"{'':<18} report: {result['pdf_path']}\n"
            f"{'':<18} explanation source: {result['explanation']['source']}"
        )


if __name__ == "__main__":
    main()
