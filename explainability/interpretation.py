"""Applicant-facing interpretation utilities (shared by API, LLM and PDF).

Turns raw model inputs and provider summaries into the context an applicant
actually needs: plain-language bands, what a value means, how composite
indicators were calculated, and reference points from the training data.
Nothing here changes a score, a feature value or a contribution direction —
interpretation only describes facts that were already computed.

Reference points come from the training-data report (EDA_Report.md) and are
always presented as context, never as eligibility thresholds.
"""

from explanation_utils import FEATURE_LABELS

# training-data reference points (EDA_Report.md, descriptive statistics)
TRAINING_REFERENCES = {
    "monthly_income_median": 63_322,
    "monthly_income_q1": 47_337,
    "monthly_income_q3": 83_138,
    "debt_to_income_median": 0.162,
    "debt_to_income_q3": 0.261,
    "loan_size_median": 494_989,
    "age_median": 38,
    "digital_purchase_median": 3,
    "digital_purchase_q3": 6,
    "psychometric_median": 58.0,
}

REFERENCE_DISCLAIMER = (
    "This is a reference point from the model's training data, not an "
    "eligibility threshold."
)

SUPPORTED_LOAN_RANGE = (50_000, 1_200_000)


# ------------------------------------------------------------------ bands
# plain activity/level bands for sub-features — deliberately NOT the final
# score's risk bands (an indicator is a model input, not a risk decision)

def activity_band(value: float) -> str:
    """Low / Moderate / High activity band for the 0-1 provider indicators."""
    if value < 1 / 3:
        return "Low"
    if value <= 2 / 3:
        return "Moderate"
    return "High"


def psychometric_band(value: float) -> str:
    if value < 40:
        return "Low"
    if value <= 65:
        return "Moderate"
    return "High"


def purchases_band(value: float) -> str:
    if value <= 1:
        return "Low"
    if value <= 6:
        return "Moderate"
    return "High"


def income_position(value: float) -> str:
    """below / around / above the typical training-data income level."""
    median = TRAINING_REFERENCES["monthly_income_median"]
    if value < 0.75 * median:
        return "below"
    if value <= 1.25 * median:
        return "around"
    return "above"


def dti_position(value: float) -> str:
    """below / around / above the typical training-data debt burden."""
    if value <= 0.10:
        return "below"
    if value <= TRAINING_REFERENCES["debt_to_income_q3"]:
        return "around"
    return "above"


# ------------------------------------------------- per-feature interpretation

def build_feature_interpretation(name: str, value) -> dict:
    """Plain-language context for one model input (never a score change)."""
    if name == "monthly_income":
        position = income_position(value)
        return {
            "label": "Monthly Income",
            "value": f"PKR {value:,.0f}",
            "band": f"{position.capitalize()} the typical level",
            "meaning": (
                f"Your reported monthly income is {position} the typical "
                "income level represented in the model's training data."
            ),
            "reference_note": (
                f"Training-data median: approximately PKR "
                f"{TRAINING_REFERENCES['monthly_income_median']:,}. "
                f"{REFERENCE_DISCLAIMER}"
            ),
            "how_calculated": None,
        }
    if name == "debt_to_income_ratio":
        position = dti_position(value)
        return {
            "label": "Debt-to-Income Ratio",
            "value": f"{value * 100:.0f}%",
            "band": f"{position.capitalize()} the typical level",
            "meaning": (
                f"Your reported debt burden is {position} the typical debt "
                "burden represented in the model's training data."
            ),
            "reference_note": (
                f"Training-data median: "
                f"{TRAINING_REFERENCES['debt_to_income_median'] * 100:.0f}%. "
                f"{REFERENCE_DISCLAIMER}"
            ),
            "how_calculated": (
                "Monthly debt payments divided by monthly income."
            ),
        }
    if name == "loan_size":
        low, high = SUPPORTED_LOAN_RANGE
        return {
            "label": "Requested Loan",
            "value": f"PKR {value:,.0f}",
            "band": None,
            "meaning": (
                "The loan amount you requested. Applications are accepted "
                f"between PKR {low:,} and PKR {high:,} — the range the "
                "model's training data represents."
            ),
            "reference_note": (
                f"Training-data median: approximately PKR "
                f"{TRAINING_REFERENCES['loan_size_median']:,}. "
                f"{REFERENCE_DISCLAIMER}"
            ),
            "how_calculated": None,
        }
    if name == "age":
        return {
            "label": "Age",
            "value": f"{value} years",
            "band": None,
            "meaning": "Your age, as declared in your application.",
            "reference_note": None,
            "how_calculated": None,
        }
    if name == "digital_purchase_frequency":
        band = purchases_band(value)
        return {
            "label": "Digital Purchase Pattern",
            "value": f"{value} per month",
            "band": f"{band} activity",
            "meaning": (
                "How many online or mobile-wallet purchases you make in a "
                "typical month."
            ),
            "reference_note": (
                f"Training-data median: "
                f"{TRAINING_REFERENCES['digital_purchase_median']} per "
                f"month. {REFERENCE_DISCLAIMER}"
            ),
            "how_calculated": None,
        }
    if name == "psychometric_score":
        band = psychometric_band(value)
        return {
            "label": "Behavioral Assessment",
            "value": f"{value:.1f} / 100",
            "band": band,
            "meaning": (
                "Your result on the 12-question Financial Behavior "
                "Assessment, which looks at money habits such as planning, "
                "saving and spending discipline. It is a prototype "
                "instrument, not a scientifically validated psychometric "
                "test — and it is only one input among many."
            ),
            "reference_note": (
                f"Training-data median: "
                f"{TRAINING_REFERENCES['psychometric_median']:.0f} / 100. "
                f"{REFERENCE_DISCLAIMER}"
            ),
            "how_calculated": (
                "Your answers to 12 questions, each on a 1-5 scale, are "
                "combined into a 0-100 score."
            ),
        }
    if name == "telecom_usage_score":
        return {
            "label": "Telecom Usage Indicator",
            "value": f"{value:.2f}",
            "band": f"{activity_band(value)} activity",
            "meaning": (
                "A composite indicator summarizing your telecom usage. See "
                "the full explanation in your report for how it is "
                "calculated."
            ),
            "reference_note": None,
            "how_calculated": None,
        }
    if name == "mobile_wallet_activity":
        return {
            "label": "Mobile Wallet Activity Indicator",
            "value": f"{value:.2f}",
            "band": f"{activity_band(value)} activity",
            "meaning": (
                "A composite indicator summarizing your mobile wallet "
                "activity. See the full explanation in your report for how "
                "it is calculated."
            ),
            "reference_note": None,
            "how_calculated": None,
        }
    if name == "occupation":
        return {
            "label": "Occupation",
            "value": str(value),
            "band": None,
            "meaning": "Your occupation, as declared in your application.",
            "reference_note": None,
            "how_calculated": None,
        }
    if name == "existing_loan_history":
        return {
            "label": "Credit History",
            "value": str(value),
            "band": None,
            "meaning": (
                "Your credit-history classification, determined by the "
                "credit information verification step."),
            "reference_note": None,
            "how_calculated": (
                "Derived deterministically from the six verified "
                "credit-information fields."),
        }
    # anything else: a plain declared value
    return {
        "label": name.replace("_", " ").title(),
        "value": str(value),
        "band": None,
        "meaning": "",
        "reference_note": None,
        "how_calculated": None,
    }


# --------------------------------------------- provider indicator explanations

TELECOM_COMPONENTS = [
    {"key": "recharge_consistency", "name": "Recharge consistency",
     "weight": 0.30,
     "description": "How regularly you recharge, based on your digital "
                    "purchase frequency."},
    {"key": "account_type", "name": "Account type", "weight": 0.20,
     "description": "Prepaid accounts score a base value, adjusted by how "
                    "consistent your recharges are."},
    {"key": "sim_tenure", "name": "SIM tenure", "weight": 0.25,
     "description": "How long your connection has been active, estimated "
                    "from your age."},
    {"key": "avg_recharge", "name": "Average recharge amount", "weight": 0.25,
     "description": "Your typical recharge amount, estimated from your "
                    "declared monthly income."},
]

WALLET_COMPONENTS = [
    {"key": "transaction_frequency", "name": "Transaction frequency",
     "weight": 0.30,
     "description": "How regularly the wallet is used, based on your "
                    "digital purchase frequency."},
    {"key": "average_balance", "name": "Average balance", "weight": 0.25,
     "description": "The average balance maintained in the wallet, "
                    "estimated from your declared income."},
    {"key": "inflow_outflow", "name": "Inflow vs outflow", "weight": 0.25,
     "description": "Compares money received with money spent, estimated "
                    "from your debt burden."},
    {"key": "account_age", "name": "Wallet account age", "weight": 0.20,
     "description": "How long the wallet account has been active, "
                    "estimated from your activity level."},
]

PROVIDER_SIMULATION_NOTE = (
    "Simulated for this prototype — no telecom operator or wallet provider "
    "is contacted. The indicator is computed deterministically from your "
    "declared profile (digital purchases, income, age and debt burden), so "
    "the same declared information always produces the same indicator."
)

# used when the indicator was supplied as a plain model input (e.g. the CLI
# demo feeds the dataset-generated value) — never invent component data
MODEL_INPUT_NOTE = (
    "This is a composite indicator used by the current scoring model. This "
    "demonstration receives the indicator as a model input rather than "
    "calculating it from raw operator records."
)


def _indicator(components_meta, scores, score, label, formula, meaning):
    return {
        "label": label,
        "value": f"{score:.2f}",
        "band": f"{activity_band(score)} activity",
        "meaning": meaning,
        "simulation_note": PROVIDER_SIMULATION_NOTE,
        "formula": formula,
        "components": [
            {
                "name": meta["name"],
                "weight": f"{meta['weight']:.0%}",
                "description": meta["description"],
                "score": round(scores[meta["key"]], 1),
            }
            for meta in components_meta
        ],
    }


def build_telecom_explanation(score: float, component_scores: dict) -> dict:
    """The 'How is this calculated?' explanation for the telecom indicator."""
    return _indicator(
        TELECOM_COMPONENTS, component_scores, score, "Telecom Usage Indicator",
        "0.30 x Recharge consistency + 0.20 x Account type + 0.25 x SIM "
        "tenure + 0.25 x Average recharge amount",
        "A composite indicator summarizing your telecom usage, calculated "
        "from the components below.",
    )


def build_wallet_activity_explanation(score: float,
                                      component_scores: dict) -> dict:
    """The 'How is this calculated?' explanation for the wallet indicator."""
    return _indicator(
        WALLET_COMPONENTS, component_scores, score,
        "Mobile Wallet Activity Indicator",
        "0.30 x Transaction frequency + 0.25 x Average balance + 0.25 x "
        "Inflow/outflow ratio + 0.20 x Account age",
        "A composite indicator summarizing your mobile wallet activity, "
        "calculated from the components below.",
    )


def _input_only_indicator(score: float, label: str) -> dict:
    """Honest fallback when no component data exists (indicator as input)."""
    return {
        "label": label,
        "value": f"{score:.2f}",
        "band": f"{activity_band(score)} activity",
        "simulation_note": MODEL_INPUT_NOTE,
        "formula": None,
        "components": [],
        "meaning": (
            "A composite indicator summarizing usage patterns, used by the "
            "model as one input among many."),
        "reference_note": None,
        "how_calculated": MODEL_INPUT_NOTE,
    }


# ----------------------------------------------------- credit history display

CREDIT_DEMO_NOTICE = (
    "Demo Credit Verification — credit-history information shown here is "
    "simulated for demonstration purposes and is not retrieved from a real "
    "credit bureau."
)

_CREDIT_ROWS = [
    ("has_previous_loan", "Previous loan", lambda v: "Yes" if v else "No"),
    ("has_credit_card", "Credit card", lambda v: "Yes" if v else "No"),
    ("total_outstanding_amount", "Outstanding amount",
     lambda v: f"PKR {v:,.0f}"),
    ("installments_paid_on_time", "Installments paid on time",
     lambda v: f"{v}"),
    ("has_overdue_or_default", "Overdue/default detected",
     lambda v: "Yes" if v else "No"),
    ("total_existing_debt", "Total existing debt",
     lambda v: f"PKR {v:,.0f}"),
]


def build_credit_history_explanation(credit_data: dict, derived: str) -> dict:
    """Display rows + narrative for one verified credit record."""
    rows = [
        {"label": label, "value": formatter(credit_data[key])}
        for key, label, formatter in _CREDIT_ROWS
    ]
    return {
        "rows": rows,
        "narrative": (
            "Based on these credit-history indicators, the system "
            f"classified your repayment history as {derived}."
        ),
        "demo_notice": CREDIT_DEMO_NOTICE,
    }


# ------------------------------------------------------ score pipeline blocks

SCORE_PIPELINE = [
    ("Financial Information", "Income, debt burden and requested loan"),
    ("Credit History", "Verified credit-information record"),
    ("Digital Activity", "Telecom, wallet and purchase indicators"),
    ("Behavioral Indicators", "Financial Behavior Assessment result"),
]

SCORE_PIPELINE_NOTE = (
    "The scoring model considers all of these inputs together — the "
    "categories above are not manually added up to produce your score."
)


# ---------------------------------------------- contributor interpretations

_STRENGTHS = ((5.0, "strong"), (2.0, "moderate"))


def _strength(magnitude: float) -> str:
    for threshold, word in _STRENGTHS:
        if magnitude >= threshold:
            return word
    return "slight"


def build_contributor_explanation(name: str, value, shap_value: float) -> dict:
    """Meaning + influence statement for one contributor (no raw SHAP).

    Direction and strength come straight from the contribution's sign and
    magnitude — this layer never overrides them (spec sections 14-15).
    """
    interp = build_feature_interpretation(name, value)
    direction = "positive" if shap_value > 0 else "negative"
    return {
        "meaning": interp["meaning"] or "Declared applicant information.",
        "reference_note": interp["reference_note"],
        "influence": (
            f"This factor had a {_strength(abs(shap_value))} {direction} "
            "influence on the model score."),
    }


# --------------------------------------------------- full interpretation set

def build_interpretation_blocks(feature_values: dict, assessment: dict,
                                credit_history: dict | None = None,
                                provider_components: dict | None = None) -> dict:
    """Every applicant-facing interpretation block for one scoring run.

    feature_values: the ten model inputs, keyed by model feature name
    assessment: the assess_applicant result (contributors carry labels)
    credit_history: credit_verification_public() output (None -> the credit
        section falls back to the plain category, e.g. for CLI demos)
    provider_components: {"telecom": {...}, "wallet": {...}} component
        scores; None -> the indicators are described as model inputs
    """
    components = provider_components or {}
    telecom = (
        build_telecom_explanation(
            feature_values["telecom_usage_score"], components["telecom"])
        if "telecom" in components else _input_only_indicator(
            feature_values["telecom_usage_score"], "Telecom Usage Indicator")
    )
    wallet = (
        build_wallet_activity_explanation(
            feature_values["mobile_wallet_activity"], components["wallet"])
        if "wallet" in components else _input_only_indicator(
            feature_values["mobile_wallet_activity"],
            "Mobile Wallet Activity Indicator")
    )

    def _interp(name):
        return build_feature_interpretation(name, feature_values[name])

    key_by_label = {label: key for key, label in FEATURE_LABELS.items()}

    def _contributor_blocks(contributors):
        blocks = []
        for c in contributors:
            key = key_by_label.get(c["feature"])
            block = {
                "feature": c["feature"],
                "value": c["value"],
                "influence": (
                    "This factor had a positive influence on the model score."
                    if c["shap_value"] > 0 else
                    "This factor had a negative influence on the model score."),
            }
            if key is not None and key in feature_values:
                block.update(build_contributor_explanation(
                    key, feature_values[key], c["shap_value"]))
            blocks.append(block)
        return blocks

    return {
        "application_info": [_interp(n) for n in
                             ("age", "occupation", "monthly_income",
                              "loan_size")],
        "credit_history": credit_history,
        "financial_indicators": [
            _interp("monthly_income"),
            _interp("debt_to_income_ratio"),
            _interp("loan_size"),
        ],
        "digital_indicators": [
            telecom,
            wallet,
            _interp("digital_purchase_frequency"),
            _interp("psychometric_score"),
        ],
        "top_supported": _contributor_blocks(
            assessment["positive_contributors"]),
        "top_reduced": _contributor_blocks(
            assessment["negative_contributors"]),
        "score_pipeline": [
            {"name": name, "description": description}
            for name, description in SCORE_PIPELINE
        ],
        "pipeline_note": SCORE_PIPELINE_NOTE,
    }
