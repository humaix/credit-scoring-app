"""Scoring + SHAP contribution analysis for a single applicant.

Uses the saved pipeline as-is: preprocessing, model and feature names all come
from the pickle. One-hot SHAP columns of a categorical variable are summed
back into that variable (SHAP values are additive), labelled with the
applicant's actual level, so no encoded names surface in the report.
"""

import joblib
import numpy as np
import pandas as pd
import shap

from explanation_utils import (
    FEATURE_LABELS, MODEL_FEATURES, MODEL_PATH, format_feature_value, score_category,
)

_pipeline = None


def _load_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = joblib.load(MODEL_PATH)
    return _pipeline


def _per_feature_contributions(shap_row, feature_names):
    """Collapse transformed-column SHAP values onto the 10 model features."""
    totals = {feature: 0.0 for feature in MODEL_FEATURES}
    for name, value in zip(feature_names, shap_row):
        if name.startswith("occupation_"):
            totals["occupation"] += float(value)
        elif name.startswith("existing_loan_history_"):
            totals["existing_loan_history"] += float(value)
        elif name in totals:
            totals[name] += float(value)
    return totals


def assess_applicant(applicant):
    """Predict the repayment score and build the structured explanation input.

    Returns repayment score, score category, applicant features and the
    strongest positive/negative contributors with their exact SHAP values.
    """
    pipe = _load_pipeline()
    X = pd.DataFrame([applicant], columns=MODEL_FEATURES)

    raw_score = float(pipe.predict(X)[0])
    score = float(np.clip(raw_score, 0.0, 100.0))
    displayed = round(score, 1)

    preprocessor = pipe.named_steps["preprocess"]
    model = pipe.named_steps["model"]
    feature_names = [n.split("__", 1)[1] for n in preprocessor.get_feature_names_out()]
    X_prepared = pd.DataFrame(preprocessor.transform(X), columns=feature_names)

    explainer = shap.TreeExplainer(model)
    shap_row = np.asarray(explainer.shap_values(X_prepared))[0]
    base_value = float(np.ravel(explainer.expected_value)[0])

    # TreeSHAP is additive: base + contributions must rebuild the model output
    if abs(base_value + shap_row.sum() - raw_score) > 1e-2:
        raise RuntimeError(
            "SHAP decomposition does not match the model prediction - "
            "contributions would be unreliable"
        )

    totals = _per_feature_contributions(shap_row, feature_names)
    all_contributions = [
        {
            "feature": FEATURE_LABELS[name],
            "value": format_feature_value(name, applicant[name]),
            "shap_value": round(value, 4),
        }
        for name, value in totals.items()
    ]

    positives = sorted(
        (c for c in all_contributions if c["shap_value"] > 0),
        key=lambda c: c["shap_value"], reverse=True,
    )[:3]
    negatives = sorted(
        (c for c in all_contributions if c["shap_value"] < 0),
        key=lambda c: c["shap_value"],
    )[:3]

    return {
        "repayment_score": displayed,
        "raw_score": round(raw_score, 4),
        "score_category": score_category(displayed),
        "applicant_features": [
            {"feature": FEATURE_LABELS[name], "value": format_feature_value(name, applicant[name])}
            for name in MODEL_FEATURES
        ],
        # raw values by model feature name — powers the structured LLM payload
        # and the applicant-facing interpretation blocks
        "feature_values": {name: applicant[name] for name in MODEL_FEATURES},
        "positive_contributors": positives,
        "negative_contributors": negatives,
        "all_contributions": sorted(
            all_contributions, key=lambda c: c["shap_value"], reverse=True
        ),
        "base_value": round(base_value, 4),
    }
