# Explainability Layer — Applicant Repayment Assessment Reports

This module wraps the trained credit-scoring model with a complete Explainable
AI (XAI) layer. For every applicant it produces a professional PDF report
containing the model-estimated repayment score (0–100), the score category, and
a human-readable explanation of *why* the model generated that score — driven
by real SHAP feature contributions, never invented reasons.

## How the system works

```text
Applicant Data
      |
      v
Input Validation (explanation_utils.py)
      |
      v
Saved XGBoost Pipeline (models/final_credit_scoring_model.pkl)  ->  Repayment Score
      |
      v
SHAP TreeExplainer (shap_explainer.py)                          ->  Feature Contributions
      |
      v
Structured Explanation Data (score, category, top contributors)
      |
      v
LLM wording layer (llm_explainer.py)                            ->  Human-readable Explanation
      |          \
      |           +--> fallback templates on any LLM failure
      v
PDF Report (report_generator.py)                                ->  generated_reports/*.pdf
```

The responsibilities are strictly separated:

- **XGBoost decides the score.** The saved pipeline is loaded read-only and is
  never retrained, modified or re-saved.
- **SHAP explains the model's feature contributions.** The exact values are
  computed per applicant and verified to rebuild the model's prediction
  (TreeSHAP is additive).
- **The LLM only converts those contributions into understandable language.**
  It never computes or changes the score, never flips a contribution's
  direction, and never makes approval decisions.

## SHAP methodology

- Per applicant, exact TreeSHAP values are computed for the tuned XGBoost
  regressor on the transformed feature matrix.
- The model's preprocessing one-hot encodes `occupation` and
  `existing_loan_history`. Because SHAP values are additive, the one-hot
  columns of each categorical variable are summed back into that variable and
  labelled with the applicant's actual level (e.g. "Occupation: Freelancer").
  No encoded feature names ever reach the applicant.
- The top 3 positive and top 3 negative contributors (by SHAP value) are
  reported. If fewer exist, only the available ones are shown.
- An internal consistency check asserts that
  `base value + sum(contributions) == model prediction` before any explanation
  is produced.
- `borrower_id`, `loan_history_code`, `gender` and `province` are excluded from
  prediction and explanation. `loan_history_code` is a duplicate numeric
  encoding of `existing_loan_history` and must never be used alongside it.

## The LLM's role (and limits)

`llm_explainer.py` sends exactly **one API request per applicant** containing
only the minimum data needed for wording: the score, the category, the
applicant's ten feature values and the top contributors. Nothing else — no
dataset rows, no identifiers, no internal system information.

The LLM operates under a strict system prompt: explain only the provided
contributions, keep their direction, use human-readable feature names, no
causal claims, no certainty claims, no approval decisions, no financial
advice, no technical jargon. Its JSON answer is validated (required keys,
types, no dropped contributors) before use.

Any OpenAI-compatible chat completions endpoint works. Configure via
environment variables — nothing is hardcoded:

| Variable | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | API key (never printed or logged) | — |
| `LLM_MODEL` | Model name, e.g. `gpt-4o-mini`, `qwen-plus` | — |
| `LLM_BASE_URL` | Provider endpoint | `https://api.openai.com/v1` |
| `LLM_TIMEOUT` | Request timeout (seconds) | `30` |

## Environment setup

```bash
pip install -r requirements-explainability.txt   # or install individually:
pip install numpy pandas joblib shap xgboost matplotlib reportlab requests python-dotenv pypdf
```

The model file `models/final_credit_scoring_model.pkl` must exist (produced by
`ML_Credit_Scoring.ipynb`). XGBoost is pinned to **2.1.4** for shap 0.49
TreeExplainer compatibility.

### Configuring `.env`

Copy the template and fill in your provider's credentials:

```bash
cp .env.example .env
```

```env
LLM_API_KEY=your_api_key_here
LLM_MODEL=your_model_name
LLM_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Common endpoints: OpenAI `https://api.openai.com/v1`; DashScope (Qwen)
`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; Groq
`https://api.groq.com/openai/v1`. `.env` is listed in `.gitignore` — never
commit it. A key already present in the process environment takes precedence
over the file.

## Generating a report

Command line:

```bash
python explainability/generate_report.py --demo                 # three sample applicants
python explainability/generate_report.py --input applicant.json # your own applicant
```

Programmatic use:

```python
from explainability import generate_repayment_report

pdf_path = generate_repayment_report(applicant_data)            # returns Path to the PDF
details = generate_repayment_report(applicant_data, return_details=True)
# details = {"pdf_path", "assessment" (score, category, contributors), "explanation"}
```

Applicant data is a dict with the ten model features (`age`, `occupation`,
`monthly_income`, `existing_loan_history`, `debt_to_income_ratio`,
`loan_size`, `telecom_usage_score`, `mobile_wallet_activity`,
`digital_purchase_frequency`, `psychometric_score`). See
`explainability/sample_applicant.json`. Extra dataset columns
(`borrower_id`, `loan_history_code`, `gender`, `province`) are ignored, so full
CSV rows can be passed directly. Invalid input (missing fields, wrong types,
out-of-range values, unknown categories) is rejected with explicit error
messages — values are never silently modified.

## Live demo app

```bash
pip install streamlit
streamlit run app.py
```

An interactive demo of the whole pipeline: edit any of the ten applicant
features and the score updates live (computed by the real saved model, never
precomputed). The app includes preset profiles, the top contributors chart,
an "Under the hood" panel (raw model output, base value, SHAP additivity
check, full contribution table) and a **reality check** that compares the
model's estimate with the actual scores of the 50 most similar training
applicants (`reality_check.py`). The "Generate PDF report" button calls the
same `generate_repayment_report()` used everywhere else.

## Fallback behavior

The PDF always generates, even fully offline. The fallback activates when the
API key is missing, the request fails, times out, returns an HTTP error, or
the LLM returns invalid/unsound JSON. It uses predefined templates driven by
the **actual SHAP signs and magnitudes**, e.g. "A debt-to-income ratio of 0.42
had a strong negative contribution to the model's repayment score." Nothing is
fabricated; every sentence's direction comes from the real contribution.

## PDF structure

Each report (`explainability/generated_reports/repayment_assessment_<timestamp>.pdf`)
contains:

1. **Repayment Assessment** — score (e.g. `78.4 / 100`), category band
   (Very Low / Low / Moderate / High / Very High), colour gauge, and a neutral
   note that this is a model-estimated assessment, not a guarantee.
2. **Applicant Information** — the ten submitted features, professionally
   formatted (e.g. `PKR 75,000`).
3. **Why This Score Was Generated** — up to three positive factors, up to
   three factors reducing the score, and an overall explanation, all derived
   from the actual SHAP contributions.
4. **Feature Contribution Analysis** — a bar chart of the strongest
   contributions for this applicant (green = raised the score, red = lowered
   it).
5. **Important Notice** — the synthetic-data / prototype disclaimer.

Reports are A4, printable, paginated, and use no internal terminology — no
encoded feature names, no "SHAP" jargon.

## Testing

```bash
python explainability/test_explainability.py
```

67 checks covering the three sample applicants (high / moderate / low
profiles), score verification against an independent model+SHAP recomputation,
PDF content extraction (score, details, disclaimer, absence of internal
names), LLM response handling via mocked endpoints, input validation, the
fallback path under a simulated outage, API-key secrecy, and confirmation that
the model file is never modified.

## Important limitations

- The underlying model was trained on **synthetic data** calibrated to
  published statistics (Khan, Tariq & Khattak 2025, Table 4.1). All scores and
  reports are prototype outputs and do **not** represent real-world lending
  performance or guarantee repayment.
- The score is a model estimate, not a probability of repayment, and not an
  approval decision. Loan decisions remain a policy layer.
- `gender` and `province` are deliberately excluded; a dedicated fairness
  audit (DPD/EOD) is recommended before any real deployment.
- Real-world use would require representative data, recalibration, governance
  and regulatory review.
