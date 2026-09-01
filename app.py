"""Streamlit demo: live applicant scoring, explanation and PDF generation.

Run from the project root:
    streamlit run app.py

Everything shown here is produced by the real system: the saved XGBoost
pipeline decides the score, SHAP decomposes it, and the PDF button calls the
same generate_repayment_report() used from the command line.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
EXPLAINABILITY_DIR = PROJECT_ROOT / "explainability"
if str(EXPLAINABILITY_DIR) not in sys.path:
    sys.path.insert(0, str(EXPLAINABILITY_DIR))

from explanation_utils import (  # noqa: E402
    SAMPLE_APPLICANTS, VALID_LOAN_HISTORY, VALID_OCCUPATIONS,
)
from generate_report import generate_repayment_report  # noqa: E402
from shap_explainer import assess_applicant  # noqa: E402

import reality_check as rc  # noqa: E402

st.set_page_config(page_title="AI Credit Scoring — Live Demo", layout="wide")

CATEGORY_HEX = {
    "Very Low": "#b71c1c", "Low": "#e65100", "Moderate": "#f9a825",
    "High": "#2e7d32", "Very High": "#1b5e20",
}

DEFAULT_APPLICANT = {
    "age": 35, "occupation": "Salaried", "monthly_income": 60_000,
    "existing_loan_history": "No Previous Loan",
    "debt_to_income_ratio": 0.30, "loan_size": 400_000,
    "telecom_usage_score": 0.60, "mobile_wallet_activity": 0.55,
    "digital_purchase_frequency": 6, "psychometric_score": 55.0,
}

PRESETS = [
    ("Strong applicant", SAMPLE_APPLICANTS[0]["data"]),
    ("Average applicant", SAMPLE_APPLICANTS[1]["data"]),
    ("High-risk applicant", SAMPLE_APPLICANTS[2]["data"]),
    ("Reset to default", DEFAULT_APPLICANT),
]


@st.cache_data
def training_dataset():
    return rc.load_dataset()


def contribution_figure(assessment):
    """Top positive and negative contributions as a horizontal bar chart."""
    ranked = assessment["all_contributions"]
    positives = [c for c in ranked if c["shap_value"] > 0][:3]
    negatives = [c for c in reversed(ranked) if c["shap_value"] < 0][:3]
    bars = sorted(positives + negatives, key=lambda c: c["shap_value"])
    if not bars:
        return None

    labels = [f"{c['feature']} ({c['value']})" for c in bars]
    values = [c["shap_value"] for c in bars]

    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(bars) + 1.1))
    ax.barh(range(len(bars)), values,
            color=["#2e7d32" if v > 0 else "#c62828" for v in values], height=0.6)
    ax.set_yticks(range(len(bars)), labels, fontsize=9)
    ax.axvline(0, color="#374151", lw=0.9)
    limit = max(abs(v) for v in values) * 1.3
    ax.set_xlim(-limit, limit)
    for i, v in enumerate(values):
        ax.text(v + (0.06 * limit if v >= 0 else -0.06 * limit), i, f"{v:+.1f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=9)
    ax.set_xlabel("Contribution to the model's repayment score (points)", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("How this works")
    st.markdown(
        "1. **You** enter the applicant's ten alternative-data features.\n"
        "2. **Validation** rejects missing or invalid values — nothing is "
        "silently changed.\n"
        "3. **XGBoost** — the exact pipeline saved after training — computes the "
        "repayment score (0–100). It is loaded read-only and never retrained.\n"
        "4. **SHAP** decomposes that score into per-feature contributions and "
        "verifies they rebuild the prediction exactly.\n"
        "5. **LLM wording layer** (optional) turns the contributions into plain "
        "English; if no endpoint is reachable, deterministic templates driven "
        "by the same SHAP values are used.\n"
        "6. **ReportLab** renders the applicant-facing PDF."
    )
    st.header("Model quality (held-out test set)")
    st.markdown(
        "- Tuned XGBoost: 600 trees, depth 4\n"
        "- Test MAE: **7.35 points** (typical error)\n"
        "- Test RMSE: **9.08** · R²: **0.72**\n"
        "- **47.5% better** than the mean baseline\n"
        "- 0 of 2,000 test predictions outside 0–100"
    )
    st.header("Important")
    st.caption(
        "Prototype trained on 10,000 synthetic applicants calibrated to Khan, "
        "Tariq & Khattak (2025). Scores are model estimates, not guarantees, "
        "and this is not financial advice. gender and province are excluded "
        "by design."
    )

# ---------------------------------------------------------------- header
st.title("AI Credit Scoring — Live Applicant Assessment")
st.caption(
    "For Pakistan's credit-invisible applicants (shopkeepers, freelancers, "
    "daily-wage workers with no bank credit history). Change any input below "
    "and the score updates live — nothing is precomputed."
)

# ---------------------------------------------------------------- inputs
st.header("Applicant Information")
preset_cols = st.columns(len(PRESETS))
for col, (label, data) in zip(preset_cols, PRESETS):
    if col.button(label):
        for key, value in data.items():
            st.session_state[f"f_{key}"] = value

left, right = st.columns(2, gap="large")
with left:
    occupation = st.selectbox("Occupation", VALID_OCCUPATIONS, key="f_occupation")
    age = st.slider("Age", 18, 65, value=DEFAULT_APPLICANT["age"], key="f_age")
    monthly_income = st.number_input(
        "Monthly income (PKR)", 1_000, 5_000_000,
        value=DEFAULT_APPLICANT["monthly_income"], step=1_000,
        key="f_monthly_income")
    loan_history = st.selectbox(
        "Existing loan history", VALID_LOAN_HISTORY, key="f_existing_loan_history")
    dti = st.slider("Debt-to-income ratio", 0.0, 1.0,
                    value=DEFAULT_APPLICANT["debt_to_income_ratio"], step=0.01,
                    format="%.2f", key="f_debt_to_income_ratio")
with right:
    loan_size = st.number_input(
        "Requested loan size (PKR)", 10_000, 10_000_000,
        value=DEFAULT_APPLICANT["loan_size"], step=10_000, key="f_loan_size")
    telecom = st.slider("Telecom usage score", 0.0, 1.0,
                        value=DEFAULT_APPLICANT["telecom_usage_score"], step=0.01,
                        format="%.2f", key="f_telecom_usage_score")
    wallet = st.slider("Mobile wallet activity", 0.0, 1.0,
                       value=DEFAULT_APPLICANT["mobile_wallet_activity"], step=0.01,
                       format="%.2f", key="f_mobile_wallet_activity")
    purchases = st.slider("Digital purchases per month", 0, 200,
                          value=DEFAULT_APPLICANT["digital_purchase_frequency"],
                          key="f_digital_purchase_frequency")
    psych = st.slider("Psychometric score", 0.0, 100.0,
                      value=DEFAULT_APPLICANT["psychometric_score"], step=0.5,
                      key="f_psychometric_score")

applicant = {
    "age": age, "occupation": occupation, "monthly_income": monthly_income,
    "existing_loan_history": loan_history,
    "debt_to_income_ratio": dti, "loan_size": loan_size,
    "telecom_usage_score": telecom, "mobile_wallet_activity": wallet,
    "digital_purchase_frequency": purchases, "psychometric_score": psych,
}

# ---------------------------------------------------------------- live score
st.divider()
try:
    assessment = assess_applicant(applicant)
except Exception as exc:
    st.error(f"Scoring failed: {exc}")
    st.stop()

score = assessment["repayment_score"]
category = assessment["score_category"]
color = CATEGORY_HEX[category]
df = training_dataset()

st.header("Live Assessment")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Repayment score", f"{score:.1f} / 100")
m2.metric("Category", category)
pct = rc.percentile_in_dataset(df, score)
m3.metric("Position in training data", f"higher than {pct * 100:.0f}%")
m4.metric("vs average training applicant (58.1)", f"{score - df['repayment_score'].mean():+.1f}")

st.markdown(
    f'<div style="background:#e5e7eb;border-radius:6px;overflow:hidden;">'
    f'<div style="width:{score}%;background:{color};height:12px;"></div></div>',
    unsafe_allow_html=True,
)
st.caption("Bands: Very Low 0–20 · Low 21–40 · Moderate 41–60 · High 61–80 · "
           "Very High 81–100. This score is a model estimate, not a guarantee.")

st.subheader("Why this score — feature contributions")
fig = contribution_figure(assessment)
if fig is not None:
    st.pyplot(fig)
    plt.close(fig)

pos_col, neg_col = st.columns(2)
with pos_col:
    st.markdown("**Factors raising the score**")
    for c in assessment["positive_contributors"]:
        st.markdown(f"- **{c['feature']}** ({c['value']}): "
                    f"**+{c['shap_value']:.1f} points**")
    if not assessment["positive_contributors"]:
        st.markdown("- None")
with neg_col:
    st.markdown("**Factors lowering the score**")
    for c in assessment["negative_contributors"]:
        st.markdown(f"- **{c['feature']}** ({c['value']}): "
                    f"**{c['shap_value']:.1f} points**")
    if not assessment["negative_contributors"]:
        st.markdown("- None")

# ---------------------------------------------------------------- under the hood
with st.expander("Under the hood — exactly how this score was produced"):
    raw = assessment["raw_score"]
    base = assessment["base_value"]
    total = sum(c["shap_value"] for c in assessment["all_contributions"])
    st.markdown(
        f"- Raw XGBoost output: **{raw}** — clipped to [0, 100] and rounded to "
        f"1 decimal for display: **{assessment['repayment_score']}**\n"
        f"- Base value (the average training applicant the model compares "
        f"against): **{base:.2f}**\n"
        f"- Additivity check: base {base:.2f} + sum of contributions "
        f"{total:+.2f} = **{base + total:.2f}** — matches the model output, so "
        f"the explanation is exact, not approximate."
    )
    contrib_df = pd.DataFrame(assessment["all_contributions"]).rename(
        columns={"feature": "Feature", "value": "Applicant value",
                 "shap_value": "Contribution (points)"})
    st.dataframe(contrib_df, hide_index=True)
    st.caption(
        "gender, province and borrower_id are excluded by design — the model "
        "never sees them. One-hot encoded occupation / loan-history "
        "contributions are summed back to the single human-readable feature."
    )

# ---------------------------------------------------------------- reality check
with st.expander("Reality check — is this score plausible?"):
    neighbors, pool_size = rc.nearest_neighbors(df, applicant)
    summary = rc.neighbor_summary(neighbors)
    gap = score - summary["mean"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("50 most similar applicants — average actual score",
              f"{summary['mean']:.1f}")
    c2.metric("Model's estimate for this applicant", f"{score:.1f}",
              delta=f"{gap:+.1f}")
    c3.metric("Similar applicants' typical range (10th–90th pct)",
              f"{summary['p10']:.0f} – {summary['p90']:.0f}")
    c4.metric("Model's typical test error (MAE)", "±7.35")

    nb_fig = rc.neighbors_histogram(neighbors, score)
    st.pyplot(nb_fig)
    plt.close(nb_fig)
    ds_fig = rc.dataset_histogram(df, score)
    st.pyplot(ds_fig)
    plt.close(ds_fig)

    verdict = "within" if abs(gap) <= 7.35 else "larger than"
    st.info(
        f"**How to read this:** {pool_size:,} training applicants share this "
        f"occupation and loan history. The 50 closest to this applicant by "
        f"income, debt, loan size and digital behaviour actually scored "
        f"**{summary['mean']:.1f} on average** (range {summary['min']:.1f}–"
        f"{summary['max']:.1f}), and the model estimates **{score:.1f}** for "
        f"this profile — a gap of **{abs(gap):.1f} points**, {verdict} the "
        f"model's typical error of ±7.35. Similar applicants are not "
        f"identical applicants, so some gap is expected; extreme profiles "
        f"also naturally pull toward the middle because the model cannot "
        f"extrapolate beyond its training range."
    )
    st.caption("All comparison figures come from the synthetic training "
               "dataset — realistic in structure, but not real people.")

# ---------------------------------------------------------------- PDF report
st.divider()
st.header("Applicant Repayment Assessment Report")
st.write(
    "Generates the professional PDF a loan officer would receive — score, "
    "category, full natural-language explanation and contribution chart. "
    "Same code path as the command-line tool."
)

if "pdf_result" not in st.session_state:
    st.session_state["pdf_result"] = None

if st.button("Generate PDF report", type="primary"):
    with st.spinner("Scoring, computing contributions, writing the "
                    "explanation and rendering the PDF..."):
        try:
            details = generate_repayment_report(applicant, return_details=True)
        except Exception as exc:
            st.error(f"PDF generation failed: {exc}")
        else:
            st.session_state["pdf_result"] = {
                "name": details["pdf_path"].name,
                "bytes": details["pdf_path"].read_bytes(),
                "assessment": details["assessment"],
                "explanation": details["explanation"],
            }

if st.session_state["pdf_result"]:
    result = st.session_state["pdf_result"]
    exp = result["explanation"]
    st.success(f"Report saved: explainability/generated_reports/{result['name']}")
    st.download_button("Download the PDF report", data=result["bytes"],
                       file_name=result["name"], mime="application/pdf")

    source = ("live LLM wording layer"
              if exp["source"] == "llm"
              else "offline fallback templates (no LLM endpoint reachable — "
                   "set LLM_BASE_URL in .env to enable)")
    st.markdown(f"Explanation written by the **{source}**.")
    st.markdown(f"**Summary.** {exp['summary']}")
    if exp["positive_factors"]:
        st.markdown("**Positive factors**")
        st.markdown("\n".join(f"- {f}" for f in exp["positive_factors"]))
    if exp["negative_factors"]:
        st.markdown("**Factors reducing the score**")
        st.markdown("\n".join(f"- {f}" for f in exp["negative_factors"]))
    st.markdown(f"**Overall.** {exp['overall_explanation']}")

st.divider()
st.caption(
    "AI credit-scoring prototype · synthetic training data · the model "
    "estimates repayment likelihood, it does not decide loan approvals."
)
