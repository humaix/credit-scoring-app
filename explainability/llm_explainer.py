"""LLM explanation writer: converts SHAP contributions into natural language.

The LLM is a wording layer only. It never computes the score, never changes a
contribution's direction and never sees more than one applicant's explanation
data. Any failure (missing key, network error, timeout, invalid JSON) falls
back to predefined SHAP-direction templates so the PDF always renders.
"""

import json
import logging
import os

import requests
from dotenv import load_dotenv

from explanation_utils import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env", override=False)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a report writer for an AI credit-scoring prototype that estimates
loan repayment scores (0-100) from alternative data. Your ONLY job is to convert
structured model-contribution data into clear, professional English for an
applicant-facing report.

STRICT RULES:
1. Use ONLY the information provided in the input. Never invent facts, values or effects.
2. Never change the direction (sign) of any contribution.
3. Never calculate, modify or question the repayment score - it is given to you.
4. Never make loan approval or rejection decisions or recommendations.
5. Never claim certainty about future repayment or any outcome.
6. Never make causal claims. Describe how features CONTRIBUTED to the model's score,
   never what they will cause. GOOD: "had a negative contribution to the model's score".
   BAD: "will cause you to default".
7. Use the human-readable feature names exactly as given. Never mention internal
   encodings, one-hot names or technical terms such as "SHAP".
8. Do not exaggerate importance; a larger absolute contribution means a stronger influence.
9. Use simple, professional, neutral language. Do not give financial advice.
10. Treat every applicant the same way regardless of the score level.

OUTPUT FORMAT - return ONLY one valid JSON object, no extra text, no code fences:
{
  "summary": "one short paragraph (2-3 sentences)",
  "positive_factors": ["1-2 sentences each, max 3 items"],
  "negative_factors": ["1-2 sentences each, max 3 items"],
  "overall_explanation": "one short paragraph (2-3 sentences)"
}
If there are no positive or no negative contributors, use an empty list for that key."""

# keys required in the LLM's JSON answer
RESPONSE_KEYS = ("summary", "positive_factors", "negative_factors", "overall_explanation")


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM is not configured or cannot be reached."""


def _settings():
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "timeout": float(os.getenv("LLM_TIMEOUT", "30")),
    }


def _llm_payload(assessment):
    """Minimum data needed for wording - nothing else is sent to the provider."""
    return {
        "repayment_score": assessment["repayment_score"],
        "score_category": assessment["score_category"],
        "applicant_features": assessment["applicant_features"],
        "positive_contributors": assessment["positive_contributors"],
        "negative_contributors": assessment["negative_contributors"],
    }


def _post_chat_completion(messages):
    """Single call to an OpenAI-compatible chat completions endpoint."""
    cfg = _settings()
    if not cfg["api_key"] or not cfg["model"]:
        raise LLMUnavailableError("LLM_API_KEY / LLM_MODEL not configured")

    response = requests.post(
        f"{cfg['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}"},
        json={
            "model": cfg["model"],
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
        },
        timeout=cfg["timeout"],
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _extract_json(text):
    # tolerate code fences or prose around the JSON object
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the LLM response")
    return json.loads(text[start:end + 1])


def _validate_llm_explanation(parsed, n_positive, n_negative):
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    for key in RESPONSE_KEYS:
        if key not in parsed:
            raise ValueError(f"LLM response is missing key: {key}")

    out = {}
    for key in ("summary", "overall_explanation"):
        value = str(parsed[key]).strip()
        if not value:
            raise ValueError(f"LLM response has an empty {key}")
        out[key] = value

    for key, expected in (("positive_factors", n_positive), ("negative_factors", n_negative)):
        items = parsed[key]
        if not isinstance(items, list):
            raise ValueError(f"LLM response field {key} is not a list")
        strings = [str(item).strip() for item in items if str(item).strip()]
        if expected > 0 and not strings:
            raise ValueError(f"LLM response dropped existing {key}")
        out[key] = strings[:3]  # never more than 3 factors per side

    return out


# ----------------------------------------------------------------------
# fallback templates - direction comes from the actual SHAP sign
# ----------------------------------------------------------------------
_STRENGTHS = ((5.0, "strong"), (2.0, "moderate"))

_FEATURE_SENTENCES = {
    "Monthly Income": (
        "A monthly income of {value} made a {strength} positive contribution to the model's repayment score.",
        "A monthly income of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Debt-to-Income Ratio": (
        "A debt-to-income ratio of {value} made a {strength} positive contribution to the model's repayment score, reflecting comparatively light existing debt obligations relative to income.",
        "A debt-to-income ratio of {value} made a {strength} negative contribution to the model's repayment score, as existing debt obligations take up a substantial share of income at this level.",
    ),
    "Loan Size": (
        "The requested loan size of {value} made a {strength} positive contribution to the model's repayment score for this profile.",
        "The requested loan size of {value} made a {strength} negative contribution to the model's repayment score for this profile.",
    ),
    "Telecom Usage Score": (
        "A telecom usage score of {value} made a {strength} positive contribution to the model's repayment score.",
        "A telecom usage score of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Mobile Wallet Activity": (
        "A mobile wallet activity level of {value} made a {strength} positive contribution to the model's repayment score.",
        "A mobile wallet activity level of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Digital Purchase Frequency": (
        "A digital purchase frequency of {value} made a {strength} positive contribution to the model's repayment score.",
        "A digital purchase frequency of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Psychometric Score": (
        "A psychometric assessment score of {value} made a {strength} positive contribution to the model's repayment score.",
        "A psychometric assessment score of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Age": (
        "An age of {value} made a {strength} positive contribution to the model's repayment score.",
        "An age of {value} made a {strength} negative contribution to the model's repayment score.",
    ),
    "Occupation": (
        "The applicant's occupation ({value}) made a {strength} positive contribution to the model's assessment.",
        "The applicant's occupation ({value}) made a {strength} negative contribution to the model's assessment.",
    ),
    "Existing Loan History": (
        "An existing loan history of '{value}' made a {strength} positive contribution to the model's assessment.",
        "An existing loan history of '{value}' made a {strength} negative contribution to the model's assessment.",
    ),
}

_DEFAULT_SENTENCE = (
    "{feature} ({value}) made a {strength} positive contribution to the model's repayment score.",
    "{feature} ({value}) made a {strength} negative contribution to the model's repayment score.",
)


def _strength(shap_value):
    magnitude = abs(shap_value)
    for threshold, word in _STRENGTHS:
        if magnitude >= threshold:
            return word
    return "slight"


def _sentence(contrib, positive):
    feature, value = contrib["feature"], contrib["value"]
    pair = _FEATURE_SENTENCES.get(feature, _DEFAULT_SENTENCE)
    template = pair[0] if positive else pair[1]
    return template.format(
        feature=feature, value=value, strength=_strength(contrib["shap_value"])
    )


def fallback_explanation(assessment):
    """Template wording driven directly by the SHAP signs and magnitudes."""
    positives = assessment["positive_contributors"]
    negatives = assessment["negative_contributors"]
    score = assessment["repayment_score"]
    category = assessment["score_category"]

    positive_factors = [_sentence(c, positive=True) for c in positives]
    negative_factors = [_sentence(c, positive=False) for c in negatives]

    pos_total = sum(c["shap_value"] for c in positives)
    neg_total = sum(c["shap_value"] for c in negatives)

    summary = (
        f"The model estimated a repayment score of {score}/100, placing this "
        f"application in the {category} assessment band. The score reflects the "
        f"combined contribution of the applicant's profile rather than any "
        f"single factor."
    )
    if positives and negatives:
        summary += (
            f" The strongest positive influence came from {positives[0]['feature']}; "
            f"the strongest negative influence from {negatives[0]['feature']}."
        )
    elif positives:
        summary += f" The strongest positive influence came from {positives[0]['feature']}."
    elif negatives:
        summary += f" The strongest negative influence came from {negatives[0]['feature']}."

    if not positives and not negatives:
        overall = (
            "This profile is close to the average profile the model learned during "
            f"training, so no single feature moved the score materially, resulting "
            f"in a {category} estimate of {score}/100."
        )
    elif positives and not negatives:
        overall = (
            f"The leading positive factors contributed +{pos_total:.1f} score points in "
            f"total, and no features meaningfully reduced the score, producing a "
            f"{category} estimate of {score}/100."
        )
    elif negatives and not positives:
        overall = (
            f"The leading negative factors contributed {neg_total:.1f} score points in "
            f"total and dominated this assessment, producing a {category} estimate "
            f"of {score}/100."
        )
    elif pos_total > abs(neg_total) + 1.0:
        overall = (
            f"The leading positive factors (+{pos_total:.1f} score points) outweighed "
            f"the leading negative factors ({neg_total:.1f} points), producing a "
            f"{category} estimate of {score}/100."
        )
    elif abs(neg_total) > pos_total + 1.0:
        overall = (
            f"The leading negative factors ({neg_total:.1f} score points) outweighed "
            f"the leading positive factors (+{pos_total:.1f} points), producing a "
            f"{category} estimate of {score}/100."
        )
    else:
        overall = (
            f"The leading positive (+{pos_total:.1f} points) and negative "
            f"({neg_total:.1f} points) factors were closely balanced, producing a "
            f"{category} estimate of {score}/100."
        )

    return {
        "summary": summary,
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "overall_explanation": overall,
        "source": "fallback",
    }


def generate_natural_language_explanation(assessment):
    """One LLM request for the full explanation; templates on any failure."""
    payload = _llm_payload(assessment)
    try:
        raw = _post_chat_completion([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                "Applicant model-contribution data:\n\n"
                + json.dumps(payload, indent=2)
                + "\n\nWrite the report explanation now. Return only the JSON object."},
        ])
        parsed = _validate_llm_explanation(
            _extract_json(raw),
            len(payload["positive_contributors"]),
            len(payload["negative_contributors"]),
        )
        parsed["source"] = "llm"
        return parsed
    except Exception as exc:  # any problem -> safe templates, PDF still renders
        logger.warning(
            "LLM explanation unavailable (%s: %s); using SHAP fallback templates",
            type(exc).__name__, str(exc)[:200],
        )
        return fallback_explanation(assessment)
