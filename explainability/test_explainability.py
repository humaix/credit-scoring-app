"""End-to-end tests for the explainability layer.

Run from the project root:
    python explainability/test_explainability.py

Covers the three sample applicants (prediction, SHAP, explanation, PDF),
independent SHAP recomputation, LLM behavior via mocked responses, input
validation, the fallback path and API-key secrecy. No network dependency:
live LLM calls may occur when a working key is configured, but every test
passes with the fallback templates as well.
"""

import hashlib
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# bound the wait if a configured LLM endpoint is unreachable during tests
os.environ["LLM_TIMEOUT"] = "15"

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import llm_explainer  # noqa: E402
from explanation_utils import (  # noqa: E402
    FEATURE_LABELS, MODEL_FEATURES, MODEL_PATH, SAMPLE_APPLICANTS,
    validate_applicant_data,
)
from generate_report import generate_repayment_report  # noqa: E402
from shap_explainer import assess_applicant  # noqa: E402

FORBIDDEN_IN_PDF = [
    "occupation_", "existing_loan_history_", "loan_history_code",
    "borrower_id", "gender", "province", "SHAP", "shap", "__",
    # overclaiming guard: the required disclaimer negates the phrase
    # ("is NOT a guaranteed probability"), so only a positive claim matches
    "is a guaranteed probability", "will cause",
]
_LABEL_TO_RAW = {display: raw for raw, display in FEATURE_LABELS.items()}

_checks = []


def check(name, condition, detail=""):
    _checks.append((name, bool(condition)))
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def _pdf_text(path):
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _independent_assessment(applicant):
    """Recompute score + SHAP outside the explainability modules."""
    pipe = joblib.load(MODEL_PATH)
    X = pd.DataFrame([applicant], columns=MODEL_FEATURES)
    score = float(pipe.predict(X)[0])

    preprocessor = pipe.named_steps["preprocess"]
    model = pipe.named_steps["model"]
    names = [n.split("__", 1)[1] for n in preprocessor.get_feature_names_out()]
    X_prepared = pd.DataFrame(preprocessor.transform(X), columns=names)
    explainer = shap.TreeExplainer(model)
    row = np.asarray(explainer.shap_values(X_prepared))[0]
    base = float(np.ravel(explainer.expected_value)[0])

    totals = {}
    for name, value in zip(names, row):
        if name.startswith("occupation_"):
            totals["occupation"] = totals.get("occupation", 0.0) + float(value)
        elif name.startswith("existing_loan_history_"):
            totals["existing_loan_history"] = totals.get("existing_loan_history", 0.0) + float(value)
        else:
            totals[name] = totals.get(name, 0.0) + float(value)
    return score, base, totals


def test_three_applicants():
    results = {}
    for sample in SAMPLE_APPLICANTS:
        label = sample["label"]
        result = generate_repayment_report(sample["data"], return_details=True)
        results[label] = result
        pdf_path = result["pdf_path"]
        assessment = result["assessment"]
        explanation = result["explanation"]

        text = _pdf_text(pdf_path)
        flat = " ".join(text.split())

        # no embedded chart image any more (raw contribution numbers are
        # hidden from applicants) - a full multi-section report is ~8 KB
        check(f"{label}: PDF created",
              pdf_path.exists() and pdf_path.stat().st_size > 5_000)
        check(f"{label}: score within 0-100",
              0 <= assessment["repayment_score"] <= 100)
        check(f"{label}: PDF opens", len(PdfReader(str(pdf_path)).pages) >= 1)
        check(f"{label}: PDF shows the exact score",
              f"{assessment['repayment_score']:.1f} / 100" in flat)
        check(f"{label}: PDF shows the category",
              f"Assessment: {assessment['score_category']}" in flat)

        income = next(f["value"] for f in assessment["applicant_features"]
                      if f["feature"] == "Monthly Income")
        check(f"{label}: applicant income in PDF", income in flat, income)
        check(f"{label}: occupation in PDF", sample["data"]["occupation"] in flat)
        check(f"{label}: disclaimer in PDF", "does not guarantee" in flat)

        bad = [token for token in FORBIDDEN_IN_PDF if token in flat]
        check(f"{label}: no internal names or terminology in PDF",
              not bad, f"found: {bad}" if bad else "")

        # score and contributions verified against an independent recomputation
        # (raw_score is stored rounded to 4 decimals in the payload)
        applicant = validate_applicant_data(sample["data"])
        score, base, totals = _independent_assessment(applicant)
        check(f"{label}: score matches the model prediction",
              abs(score - assessment["raw_score"]) < 1e-3)
        check(f"{label}: SHAP contributions rebuild the score",
              abs(base + sum(totals.values()) - score) < 1e-2)
        directions_ok = (
            all(c["shap_value"] > 0 for c in assessment["positive_contributors"])
            and all(c["shap_value"] < 0 for c in assessment["negative_contributors"])
        )
        check(f"{label}: contributor directions correct", directions_ok)
        top = assessment["positive_contributors"] + assessment["negative_contributors"]
        values_match = all(
            abs(c["shap_value"] - totals[_LABEL_TO_RAW[c["feature"]]]) < 1e-3 for c in top
        )
        check(f"{label}: contributor values match independent SHAP", values_match)

        check(f"{label}: at most 3 factors per side",
              len(explanation["positive_factors"]) <= 3
              and len(explanation["negative_factors"]) <= 3)
        if explanation["source"] == "fallback":
            if assessment["positive_contributors"]:
                check(f"{label}: fallback cites the top positive contributor",
                      assessment["positive_contributors"][0]["value"]
                      in explanation["positive_factors"][0])
            if assessment["negative_contributors"]:
                check(f"{label}: fallback cites the top negative contributor",
                      assessment["negative_contributors"][0]["value"]
                      in explanation["negative_factors"][0])

        print(f"    -> score {assessment['repayment_score']:.1f} "
              f"({assessment['score_category']}), "
              f"explanation source: {explanation['source']}, "
              f"pdf: {pdf_path.name}")

    high = results["High profile"]["assessment"]["repayment_score"]
    moderate = results["Moderate profile"]["assessment"]["repayment_score"]
    low = results["Low profile"]["assessment"]["repayment_score"]
    check("model orders the three profiles high > moderate > low",
          high > moderate > low, f"{high:.1f} / {moderate:.1f} / {low:.1f}")
    return results


def test_llm_paths(assessment):
    original = llm_explainer._post_chat_completion
    try:
        valid = json.dumps({
            "summary": "Synthetic summary for testing.",
            "positive_factors": ["Monthly Income of PKR 65,000 supported the score."],
            "negative_factors": ["The Debt-to-Income Ratio reduced the score."],
            "overall_explanation": "Synthetic overall explanation.",
        })
        llm_explainer._post_chat_completion = lambda messages: valid
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: valid JSON accepted",
              out.get("source") == "llm" and out["summary"].startswith("Synthetic"))

        llm_explainer._post_chat_completion = (
            lambda messages: "```json\n{ this is not valid json\n```")
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: invalid JSON falls back", out["source"] == "fallback")

        def _boom(messages):
            raise RuntimeError("simulated request failure")
        llm_explainer._post_chat_completion = _boom
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: request failure falls back", out["source"] == "fallback")

        incomplete = json.dumps({
            "summary": "s", "positive_factors": [],
            "negative_factors": [], "overall_explanation": "o"})
        llm_explainer._post_chat_completion = lambda messages: incomplete
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: dropped contributors rejected", out["source"] == "fallback")

        # sentences must anchor to known feature labels - invented feature
        # names (or technical jargon) force the safe fallback templates
        invented = json.dumps({
            "summary": "Fine summary.",
            "positive_factors": ["The applicant's Rocket Science Quotient helped."],
            "negative_factors": [],
            "overall_explanation": "Fine overall explanation."})
        llm_explainer._post_chat_completion = lambda messages: invented
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: invented feature name rejected", out["source"] == "fallback")

        jargon = json.dumps({
            "summary": "Mentions shap values in the summary.",
            "positive_factors": ["Monthly Income of PKR 65,000 supported the score."],
            "negative_factors": [],
            "overall_explanation": "Fine overall explanation."})
        llm_explainer._post_chat_completion = lambda messages: jargon
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("LLM: technical terminology rejected", out["source"] == "fallback")
    finally:
        llm_explainer._post_chat_completion = original


def test_validation():
    base = SAMPLE_APPLICANTS[0]["data"]
    cases = [
        ("missing field", {k: v for k, v in base.items() if k != "age"}),
        ("unknown field", {**base, "occpuption": "Salaried"}),
        ("bad occupation", {**base, "occupation": "Astronaut"}),
        ("bad loan history", {**base, "existing_loan_history": "Excellent History"}),
        ("negative income", {**base, "monthly_income": -500}),
        ("dti above 1", {**base, "debt_to_income_ratio": 1.4}),
        ("age below 18", {**base, "age": 15}),
        ("psychometric above 100", {**base, "psychometric_score": 130}),
        ("number as string", {**base, "monthly_income": "75000"}),
    ]
    for name, data in cases:
        try:
            validate_applicant_data(data)
            check(f"validation rejects: {name}", False)
        except ValueError:
            check(f"validation rejects: {name}", True)

    with_extras = {**base, "borrower_id": "PK-00001", "loan_history_code": 1,
                   "gender": "Male", "province": "Punjab"}
    normalized = validate_applicant_data(with_extras)
    check("dataset-style extra columns ignored", list(normalized) == MODEL_FEATURES)


def test_outage_and_secrecy():
    """Full pipeline under a simulated LLM outage, with a fake key in env."""
    original_post = llm_explainer._post_chat_completion
    secret = "sk-TEST-KEY-NEVER-LEAK-42"
    saved_key = os.environ.get("LLM_API_KEY")
    saved_model = os.environ.get("LLM_MODEL")
    os.environ["LLM_API_KEY"] = secret
    os.environ["LLM_MODEL"] = os.environ.get("LLM_MODEL", "test-model")

    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        def _refuse(messages):
            raise RuntimeError("simulated outage")
        llm_explainer._post_chat_completion = _refuse
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            result = generate_repayment_report(SAMPLE_APPLICANTS[1]["data"],
                                               return_details=True)
        captured = stdout_buf.getvalue() + stderr_buf.getvalue()
        check("outage: PDF still generated", result["pdf_path"].exists())
        check("outage: fallback explanation used",
              result["explanation"]["source"] == "fallback")
        check("outage: API key never printed", secret not in captured)
    finally:
        llm_explainer._post_chat_completion = original_post
        for name, saved in (("LLM_API_KEY", saved_key), ("LLM_MODEL", saved_model)):
            if saved is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved


def test_missing_key(assessment):
    saved_key = os.environ.get("LLM_API_KEY")
    saved_model = os.environ.get("LLM_MODEL")
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("LLM_MODEL", None)
    try:
        out = llm_explainer.generate_natural_language_explanation(assessment)
        check("missing key: fallback explanation used", out["source"] == "fallback")
    finally:
        for name, saved in (("LLM_API_KEY", saved_key), ("LLM_MODEL", saved_model)):
            if saved is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved


def main():
    print("=" * 72)
    print("Explainability layer - end-to-end tests")
    print("=" * 72)
    model_md5_before = _md5(MODEL_PATH)

    results = test_three_applicants()
    moderate_assessment = results["Moderate profile"]["assessment"]

    test_llm_paths(moderate_assessment)
    test_validation()
    test_outage_and_secrecy()
    test_missing_key(moderate_assessment)

    check("model file unmodified (not retrained)", _md5(MODEL_PATH) == model_md5_before)

    failed = [name for name, ok in _checks if not ok]
    print("-" * 72)
    print(f"{len(_checks) - len(failed)}/{len(_checks)} checks passed")
    if failed:
        print("FAILED CHECKS:")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
