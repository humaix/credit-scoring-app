"""Spec §18 E — LLM wording layer.

Structured response validation, hallucinated or invalid responses are
rejected, and the fallback works whenever the LLM is unavailable. The LLM
only words the SHAP contributions — it never computes or changes the score.
"""

import json

import llm_explainer
from llm_explainer import generate_natural_language_explanation

ASSESSMENT = {
    "repayment_score": 62.0, "raw_score": 62.03, "score_category": "Moderate",
    "applicant_features": [],
    "positive_contributors": [
        {"feature": "Monthly Income", "value": "PKR 90,000",
         "shap_value": 6.2},
        {"feature": "Psychometric Score", "value": "72.0",
         "shap_value": 3.1},
    ],
    "negative_contributors": [
        {"feature": "Debt-to-Income Ratio", "value": "0.35",
         "shap_value": -4.4},
    ],
    "all_contributions": [], "base_value": 58.0,
}


def _respond_with(payload):
    llm_explainer._post_chat_completion = (
        lambda messages: json.dumps(payload))


def _respond_with_raw(text):
    llm_explainer._post_chat_completion = lambda messages: text


VALID_RESPONSE = {
    "summary": "The model estimated a repayment score of 62.0/100.",
    "positive_factors": [
        "A monthly income of PKR 90,000 made a strong positive contribution "
        "to the model's repayment score.",
    ],
    "negative_factors": [
        "A debt-to-income ratio of 0.35 made a moderate negative contribution "
        "to the model's repayment score.",
    ],
    "overall_explanation": "The positive factors outweighed the negative ones.",
}


# ------------------------------------------------ structured response accepted

def test_valid_structured_response_accepted():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with(VALID_RESPONSE)
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "llm"
        assert result["summary"].startswith("The model estimated")
        assert len(result["positive_factors"]) == 1
        assert len(result["negative_factors"]) == 1
    finally:
        llm_explainer._post_chat_completion = original


def test_extra_keys_are_ignored():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with({**VALID_RESPONSE, "hallucinated_key": "junk"})
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "llm"
        assert "hallucinated_key" not in result
    finally:
        llm_explainer._post_chat_completion = original


def test_fenced_json_is_tolerated():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with_raw(f"```json\n{json.dumps(VALID_RESPONSE)}\n```")
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "llm"
    finally:
        llm_explainer._post_chat_completion = original


def test_more_than_three_factors_are_truncated():
    original = llm_explainer._post_chat_completion
    try:
        payload = {
            **VALID_RESPONSE,
            "positive_factors": [f"Factor {i}." for i in range(5)],
            "negative_factors": [f"Drag {i}." for i in range(4)],
        }
        _respond_with(payload)
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "llm"
        assert len(result["positive_factors"]) == 3
        assert len(result["negative_factors"]) == 3
    finally:
        llm_explainer._post_chat_completion = original


# ---------------------------------------- invalid/hallucinated responses

def test_invalid_json_rejected():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with_raw("this is not json at all")
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


def test_missing_key_rejected():
    original = llm_explainer._post_chat_completion
    try:
        payload = {k: v for k, v in VALID_RESPONSE.items() if k != "summary"}
        _respond_with(payload)
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


def test_empty_summary_rejected():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with({**VALID_RESPONSE, "summary": "  "})
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


def test_non_list_factors_rejected():
    original = llm_explainer._post_chat_completion
    try:
        _respond_with({**VALID_RESPONSE, "positive_factors": "income helped"})
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


def test_dropped_contributors_rejected():
    """The hallucination guard: the LLM cannot dismiss an existing contributor."""
    original = llm_explainer._post_chat_completion
    try:
        _respond_with({
            **VALID_RESPONSE,
            "positive_factors": ["Something unrelated."],
            "negative_factors": [],
        })
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


# ------------------------------------------------------- unavailable LLM

def test_provider_outage_falls_back():
    original = llm_explainer._post_chat_completion

    def _boom(messages):
        raise RuntimeError("simulated provider outage")

    try:
        llm_explainer._post_chat_completion = _boom
        result = generate_natural_language_explanation(ASSESSMENT)
        assert result["source"] == "fallback"
    finally:
        llm_explainer._post_chat_completion = original


def test_missing_api_key_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    # _settings reads env at call time, so the cleared values take effect
    result = generate_natural_language_explanation(ASSESSMENT)
    assert result["source"] == "fallback"


def test_fallback_preserves_contribution_directions():
    original = llm_explainer._post_chat_completion

    def _boom(messages):
        raise RuntimeError("down")

    try:
        llm_explainer._post_chat_completion = _boom
        result = generate_natural_language_explanation(ASSESSMENT)
        assert "positive contribution" in result["positive_factors"][0]
        assert "negative contribution" in result["negative_factors"][0]
        assert "62.0/100" in result["summary"]
    finally:
        llm_explainer._post_chat_completion = original


def test_fallback_never_mentions_internal_terminology():
    original = llm_explainer._post_chat_completion

    def _boom(messages):
        raise RuntimeError("down")

    try:
        llm_explainer._post_chat_completion = _boom
        result = generate_natural_language_explanation(ASSESSMENT)
        blob = json.dumps(result)
        for forbidden in ("SHAP", "occupation_", "existing_loan_history_"):
            assert forbidden not in blob
    finally:
        llm_explainer._post_chat_completion = original
