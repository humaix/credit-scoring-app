
# AI-Based Alternative Credit Scoring System

## Project Development Documentation

### 1. Project Overview

This project aims to develop an **AI-based alternative credit scoring system** for applicants who may not have traditional banking or formal credit history.

Instead of producing only a binary decision such as:

* Loan Repay: Yes
* Loan Repay: No

the system generates a **repayment score between 0 and 100**.

The score represents the model's estimated assessment of the applicant's repayment capability based on the information provided and patterns learned during model training.

A higher score indicates a stronger estimated repayment profile, while a lower score indicates a weaker estimated repayment profile.

> **Important:** The score is a model output and should not be interpreted as a guaranteed probability of repayment.

---

# 2. Research / Paper Replication

The project is designed as a replication/prototype based on an existing research article.

The objective was to reproduce the article's modelling approach using the same major feature set while creating a **synthetic dataset** because the original dataset was not directly available.

The synthetic dataset was designed to preserve:

* The same model features
* Similar feature ranges
* Similar categorical values
* Meaningful relationships between features
* Realistic correlations between applicant characteristics and repayment score

The dataset was not intended to represent actual borrowers.

---

# 3. Dataset

A synthetic dataset was generated specifically for this project.

The model uses the following features:

| #  | Feature                            |
| -- | ---------------------------------- |
| 1  | Monthly Income                     |
| 2  | Age                                |
| 3  | Occupation                         |
| 4  | Existing Loan History              |
| 5  | Debt-to-Income Ratio               |
| 6  | Telecom Usage Score                |
| 7  | Mobile Wallet Activity             |
| 8  | Digital Purchase Frequency Pattern |
| 9  | Psychometric Score                 |
| 10 | Moderating Variable                |

The dataset also contained some additional fields for identification or analysis purposes, but these were not necessarily used as model inputs.

---

# 4. Target Variable

Unlike a traditional binary classification problem, the target variable is a **continuous numeric repayment score**.

### Target range

```text
0 ≤ Repayment Score ≤ 100
```

Interpretation:

|  Score | General Interpretation |
| -----: | ---------------------- |
|   0–19 | Very Low               |
|  20–39 | Low                    |
|  40–59 | Moderate               |
|  60–79 | High                   |
| 80–100 | Very High              |

The exact category boundaries are defined by the project implementation.

The target score was generated synthetically with relationships to the applicant's features rather than being completely random.

For example:

* Higher income may generally contribute positively.
* Higher debt-to-income ratio may generally contribute negatively.
* Stronger financial activity may contribute positively.
* Existing loan behaviour may influence the score.
* Psychometric and alternative-data features may also influence the score.

These relationships are learned by the ML model during training.

---

# 5. Data Preprocessing

Before model training, the dataset was processed to make it suitable for machine learning.

The preprocessing pipeline handles:

* Numerical features
* Categorical features
* Missing/invalid values
* Feature transformation
* Encoding of categorical variables

Categorical features such as:

```text
Occupation
Existing Loan History
```

are transformed into machine-readable representations using encoding.

The preprocessing operations are included in the saved ML pipeline so that the **same transformations are automatically applied during inference**.

---

# 6. Exploratory Data Analysis (EDA)

EDA was performed before model training to understand the synthetic dataset.

The analysis focused on:

* Dataset structure
* Data types
* Missing values
* Duplicate records
* Descriptive statistics
* Feature distributions
* Outliers
* Categorical distributions
* Correlations
* Relationship between features and repayment score

Visualizations were also generated to understand the behaviour of the dataset.

EDA was important because the dataset was synthetic and therefore needed to be checked for unrealistic or unexpected patterns before training.

---

# 7. Machine Learning Model Training

Multiple ML algorithms were trained and evaluated rather than immediately selecting one model.

The general process was:

```text
Dataset
   ↓
Preprocessing
   ↓
Train/Test Split
   ↓
Train Multiple Models
   ↓
Evaluate Models
   ↓
Compare Performance
   ↓
Hyperparameter Tuning
   ↓
Select Final Model
```

The models were evaluated using regression-oriented metrics because the target variable is continuous.

Important evaluation metrics included:

* MAE
* RMSE
* R²

The purpose was to determine which model could best learn the relationship between applicant features and the repayment score.

---

# 8. Final Model

After model comparison and tuning, **XGBoost** was selected as the final credit-scoring model.

The trained model and preprocessing steps were saved together as:

```text
models/final_credit_scoring_model.pkl
```

The saved pipeline contains the preprocessing stage and the trained XGBoost model.

During inference, the system loads this pipeline without retraining it.

---

# 9. Repayment Score Generation

When an applicant provides their information, the system sends the ten model features to the saved pipeline.

Example:

```text
Applicant Information
        ↓
Input Validation
        ↓
Saved Preprocessing Pipeline
        ↓
XGBoost Model
        ↓
Raw Prediction
        ↓
0–100 Repayment Score
```

The resulting score is constrained to the project's 0–100 scoring range.

For example:

```text
Applicant Score = 78.4 / 100
Category = High
```

The model itself determines the score.

---

# 10. Explainability Layer

After generating the score, the project uses **SHAP (SHapley Additive exPlanations)** to understand which features contributed to that particular prediction.

The process is:

```text
Applicant
   ↓
XGBoost
   ↓
Repayment Score
   ↓
SHAP TreeExplainer
   ↓
Feature Contributions
```

For each applicant, the system calculates individual feature contributions.

A positive SHAP contribution means that the feature moved the model's prediction upward.

A negative contribution means that it moved the prediction downward.

The system identifies:

* Top 3 positive contributors
* Top 3 negative contributors

---

# 11. SHAP Consistency Verification

The implementation performs an important internal check:

```text
Base Value + Sum(SHAP Contributions)
                ≈
        Model Prediction
```

If the SHAP decomposition does not match the model prediction within the defined tolerance, the system raises an error rather than producing a potentially unreliable explanation.

This ensures that the explanation is based on the actual model prediction.

---

# 12. Handling Categorical Features

The model internally one-hot encodes categorical variables.

For example:

```text
Occupation
```

may internally become several encoded columns.

The explainability layer combines those encoded SHAP contributions back into the original feature.

Therefore, the applicant does not see technical names such as:

```text
occupation_Freelancer
occupation_Salaried
occupation_Business
```

Instead, the report displays:

```text
Occupation: Freelancer
```

This makes the explanation understandable to a normal user.

---

# 13. LLM Explanation Layer

The project uses an LLM **only as a natural-language wording layer**.

The LLM does **not**:

* Calculate the repayment score
* Modify the score
* Calculate SHAP values
* Decide whether a loan should be approved
* Change positive contributions into negative ones
* Change negative contributions into positive ones

Instead:

```text
SHAP Results
     ↓
Structured Contribution Data
     ↓
LLM
     ↓
Human-readable explanation
```

The LLM receives the score, applicant feature information and actual feature contributions.

It converts these structured results into understandable English.

---

# 14. LLM Safety / Validation

The LLM is instructed to:

* Use only supplied information.
* Never invent feature effects.
* Preserve contribution direction.
* Avoid causal claims.
* Avoid certainty about repayment.
* Avoid loan approval/rejection decisions.
* Avoid financial advice.
* Avoid technical SHAP terminology in the applicant-facing explanation.

The returned JSON is validated before being used.

If the LLM response is invalid or unavailable, the system automatically uses predefined fallback templates based on the **actual SHAP contributions**.

Therefore, the PDF can still be generated even if the LLM API is unavailable.

---

# 15. PDF Applicant Report

For every applicant, the system can generate a professional PDF report.

The report contains:

### Repayment Assessment

Example:

```text
Repayment Score: 78.4 / 100
Assessment: High
```

### Applicant Information

The applicant's submitted features are displayed in a readable format.

For example:

```text
Monthly Income: PKR 75,000
Age: 31
Occupation: Freelancer
Debt-to-Income Ratio: 0.42
...
```

### Why This Score Was Generated

The report contains:

* Positive factors
* Factors reducing the score
* Overall explanation

These explanations are based on actual model contributions.

### Feature Contribution Analysis

A visual chart shows which features moved the score upward or downward.

### Important Notice

The report clearly states that:

* The model was trained using synthetic data.
* The score is an estimated model output.
* The score does not guarantee repayment.
* The score is not automatically a loan approval decision.
* Real-world deployment requires further validation.

---

# 16. Current Project Architecture

The explainability layer follows this architecture:

```text
Applicant Data
      ↓
Input Validation
      ↓
Saved XGBoost Pipeline
      ↓
Repayment Score
      ↓
SHAP TreeExplainer
      ↓
Feature Contributions
      ↓
LLM Explanation Layer
      ↓
PDF Report Generator
      ↓
Applicant Repayment Assessment PDF
```

Important separation of responsibilities:

```text
XGBoost → Generates Score

SHAP → Explains Score

LLM → Converts Explanation into Human Language

ReportLab → Generates PDF
```

---

# 17. Important Feature Handling

`existing_loan_history` is the actual categorical feature used by the model.

`loan_history_code` is treated as a duplicate numeric representation and is **not used together with `existing_loan_history`**.

The following fields are excluded from prediction/explanation:

```text
borrower_id
loan_history_code
gender
province
```

This prevents duplicate information and prevents these non-model fields from influencing the prediction.

---

# 18. Current Limitations

The biggest limitation is that the model is trained on **synthetic data**.

Therefore, a score such as:

```text
78.4 / 100
```

cannot currently be interpreted as:

```text
78.4% actual probability of repayment
```

It is better described as:

> **Model-estimated repayment score**

To interpret the score as a calibrated probability, the system would require appropriate real-world repayment data and probability calibration.

Other important limitations include:

* Synthetic data may not represent real borrowers.
* Model performance on synthetic data does not guarantee real-world performance.
* Fairness needs to be evaluated using representative data.
* Regulatory and governance requirements would need to be addressed before deployment.

---

# 19. Next Development Stage — Validation

The next stage is to validate the complete system.

Validation should test both:

### Model Validation

Whether the model produces reliable predictions according to appropriate ML metrics.

### Pipeline Validation

Whether the complete system correctly performs:

```text
Input
→ Validation
→ Prediction
→ SHAP
→ Explanation
→ PDF
```

### Explainability Validation

Whether:

```text
Model Prediction
≈
SHAP Base Value + SHAP Contributions
```

### LLM Validation

Whether the LLM:

* Preserves SHAP direction
* Does not invent information
* Does not modify the score
* Produces valid structured output

### PDF Validation

Whether the generated PDF contains:

* Correct applicant information
* Correct score
* Correct category
* Correct explanations
* Correct contribution chart
* Required disclaimer

---

# 20. End-to-End System

The final intended workflow is:

```text
                USER
                  │
                  ▼
        Applicant Loan Request
                  │
                  ▼
          Input Validation
                  │
                  ▼
       ┌─────────────────────┐
       │  XGBoost Pipeline   │
       └─────────────────────┘
                  │
                  ▼
       Repayment Score 0–100
                  │
          ┌───────┴───────┐
          ▼               ▼
        SHAP             Score
          │
          ▼
 Feature Contributions
          │
          ▼
    LLM Explanation
          │
          ▼
    PDF Report
          │
          ▼
       Applicant
```

The applicant therefore receives **both a score and an explanation of the factors that influenced that score**.

---

## 21. Example User Use Case

Suppose a user wants to request a loan.

They provide:

```text
Monthly Income: PKR 70,000
Age: 29
Occupation: Freelancer
Existing Loan History: Good
Debt-to-Income Ratio: 0.25
Telecom Usage Score: 82
Mobile Wallet Activity: 76
Digital Purchase Frequency: 64
Psychometric Score: 78
Moderating Variable: ...
```

The system processes these values through the saved model.

Suppose the model produces:

```text
Repayment Score: 81.6 / 100
Category: Very High
```

SHAP may show that:

```text
Positive:
Monthly Income       +8.2
Loan History         +5.1
Psychometric Score   +3.7

Negative:
DTI                  -2.4
Digital Purchases    -1.2
Age                  -0.5
```

The LLM then converts these **actual contributions** into human-readable text.

Finally, the system generates a PDF containing:

```text
Applicant Details
        +
81.6 / 100 Score
        +
Positive Factors
        +
Negative Factors
        +
Overall Explanation
        +
Contribution Chart
        +
Prototype Disclaimer
```

The important point is that **the LLM is not deciding that the user is creditworthy**. The ML model produces the score; SHAP explains it; the LLM only communicates that explanation.

---

### Important correction I'd make in your documentation

One thing I would **not** write in the documentation is:

> "The score represents the probability/percentage that the applicant will repay."

Instead use:

> **"The system generates a model-estimated repayment score from 0–100. A higher score indicates a stronger model-assessed repayment profile. The score is not a calibrated probability of repayment."**

Ye distinction tumhare project ke liye **bohot important** hai, especially agar tum is project ko research paper, hackathon ya interview mein present karoge.

