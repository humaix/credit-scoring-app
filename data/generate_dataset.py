"""
generate_dataset.py
========================================================================
Synthetic dataset generator for AI-based credit scoring of Pakistan's
"credit-invisible" borrowers (shopkeepers, daily-wage workers, freelancers
who use digital wallets such as Easypaisa / JazzCash but have no formal
bank account or credit history).

Replicates and extends the data-generation methodology of:

    Khan, A. W., Tariq, M., & Khattak, M. A. (2025).
    "AI-Enhanced Credit Scoring Using Alternative Data for Financial
    Inclusion in Pakistan."
    Center for Management Science Research, Vol. 3, Issue 7, pp. 236-245.

Intentional differences from the paper (project requirements):
  * The target is a CONTINUOUS repayment_score in [0, 100] instead of the
    paper's binary loan_default flag -> the downstream task is regression /
    scoring, not classification.
  * Feature-level statistics are calibrated to the paper's Table 4.1
    wherever the paper reports them (age, monthly income, loan size,
    telecom usage score, mobile wallet activity).
  * Gender and province are included ONLY as non-predictive demographic
    columns for later fairness auditing. They are generated independently
    and influence no other column and NOT the target (fairness by
    construction).

Outputs (written next to this script):
  1. synthetic_credit_scoring_dataset.csv  - 10,000-row dataset
  2. dataset_report.txt                    - statistical validation report

Reproducibility:
  * Single RNG seeded with RANDOM_STATE = 42 (numpy.random.default_rng).
  * Re-running the script reproduces the exact same CSV and report.

Generation pipeline:
  Step 1  Demographics       age (normal), occupation (categorical),
                             gender / province (independent demographics)
  Step 2  Income             log-normal, shifted by occupation and an
                             age-experience curve
  Step 3  Psychometrics      normal, weakly linked to income
  Step 4  Loan history       categorical; driven by age and a latent
                             "responsibility" factor
  Step 5  DTI                base by history category + income percentile
                             + Gaussian noise
  Step 6  Loan size          income multiple (log-normal) adjusted by
                             occupation and DTI; calibrated to the paper's
                             statistics plus a micro-loan segment. Acts as
                             the MODERATING variable through the loan
                             burden ratio loan_size / annual income.
  Step 7  Telecom / wallet   beta distributions with behavioural tilts
  Step 8  Digital purchases  negative-binomial counts driven by wallet
                             activity, income, age, psychometrics
  Step 9  Repayment score    latent index (weights + nonlinearities +
                             interactions + loan-burden moderation +
                             Gaussian noise) mapped to 0-100 via a
                             logistic squashing function
"""

import os

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
RANDOM_STATE = 42      # fixed seed -> fully reproducible dataset
N = 10_000             # number of borrower records
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(OUT_DIR, "synthetic_credit_scoring_dataset.csv")
REPORT_PATH = os.path.join(OUT_DIR, "dataset_report.txt")

rng = np.random.default_rng(RANDOM_STATE)

# Occupation priors ---------------------------------------------------------
# p           : share of the borrower population
# income_shift: log-scale shift on monthly income
# loan_adj    : log-scale shift on the requested loan multiple
# score_eff   : direct effect on the repayment latent index
OCCUPATIONS = {
    "Salaried":          {"p": 0.22, "income_shift":  0.00, "loan_adj": -0.05, "score_eff":  0.08},
    "Self-Employed":     {"p": 0.26, "income_shift":  0.06, "loan_adj":  0.05, "score_eff":  0.00},
    "Business Owner":    {"p": 0.18, "income_shift":  0.28, "loan_adj":  0.18, "score_eff":  0.04},
    "Freelancer":        {"p": 0.08, "income_shift": -0.05, "loan_adj": -0.10, "score_eff": -0.04},
    "Daily Wage Worker": {"p": 0.20, "income_shift": -0.38, "loan_adj": -0.28, "score_eff": -0.10},
    "Other":             {"p": 0.06, "income_shift": -0.18, "loan_adj": -0.15, "score_eff": -0.06},
}

# Loan-history categories ---------------------------------------------------
# code    : numeric encoding stored next to the string column
#            (ID of the category in the order listed in the project spec,
#             NOT an ordinal quality scale - "No Previous Loan" is neutral)
# dti_base: baseline debt-to-income ratio for the category
# hist_eff: effect on the repayment latent index
LOAN_HISTORY = {
    "No Previous Loan":          {"code": 0, "dti_base": 0.07, "hist_eff":  0.00},
    "Good Repayment History":    {"code": 1, "dti_base": 0.15, "hist_eff":  0.55},
    "Delayed Repayment History": {"code": 2, "dti_base": 0.28, "hist_eff": -0.60},
    "Previous Default":          {"code": 3, "dti_base": 0.38, "hist_eff": -1.00},
}

# Paper Table 4.1 calibration targets
PAPER = {
    "age":     {"mean": 37.6,    "std": 9.5},
    "income":  {"mean": 68_450,  "std": 29_800,  "lo": 15_000,  "hi": 250_000},
    "loan":    {"mean": 520_000, "std": 180_000, "lo": 50_000,  "hi": 1_200_000},
    "telecom": {"mean": 0.61,    "std": 0.14,    "lo": 0.20,    "hi": 0.98},
    "wallet":  {"mean": 0.53,    "std": 0.19,    "lo": 0.10,    "hi": 0.95},
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def z(x):
    """Population-standardize a numeric array (mean 0, std 1)."""
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 0 else 1.0)


def sigmoid(x):
    """Numerically safe logistic function."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def ascii_hist(values, bins=20, width=48, title="", fmt=".2f"):
    """Return a plain-text histogram block for the report."""
    values = np.asarray(values, dtype=float)
    lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(values, bins=edges)
    peak = max(int(counts.max()), 1)
    lines = []
    if title:
        lines.append(title)
        lines.append("-" * 78)
    for i in range(bins):
        lo_s, hi_s = format(edges[i], fmt), format(edges[i + 1], fmt)
        n = int(counts[i])
        bar = "#" * max(1, int(round(width * n / peak))) if n > 0 else ""
        lines.append(f"[{lo_s:>13} - {hi_s:>13})  {n:>5}  {bar}")
    return "\n".join(lines)


def map_values(arr, mapping):
    """Map a numpy string array through a dict (keeps row order)."""
    return np.array([mapping[v] for v in arr])


# --------------------------------------------------------------------------
# Generation pipeline
# --------------------------------------------------------------------------
def generate_dataset():
    # ======================================================================
    # Step 1 - Demographics
    # ======================================================================
    # Age ~ Normal(37.6, 9.5) standardized then clipped to [18, 65]
    age = np.rint(np.clip(37.6 + 9.5 * z(rng.normal(37.6, 9.5, N)), 18, 65)).astype(np.int64)

    # Occupation ~ Categorical (shares sum to 1.0)
    occ_names = list(OCCUPATIONS.keys())
    occ_probs = [OCCUPATIONS[o]["p"] for o in occ_names]
    occupation = rng.choice(occ_names, size=N, p=occ_probs)

    # Demographic columns for fairness auditing ONLY. They are drawn
    # independently and feed nothing else (fairness by construction).
    gender = rng.choice(["Male", "Female"], size=N, p=[0.62, 0.38])
    province = rng.choice(
        ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"],
        size=N, p=[0.53, 0.23, 0.17, 0.07],
    )

    z_age = z(age)

    # ======================================================================
    # Step 2 - Monthly income (PKR), log-normal
    # ======================================================================
    # log(income) = base noise + occupation shift + experience curve
    #               + freelancer volatility
    occ_income_shift = map_values(occupation, {o: OCCUPATIONS[o]["income_shift"] for o in OCCUPATIONS})
    experience = -0.025 * np.clip(((age - 45.0) / 10.0) ** 2, 0, 14)   # peaks ~age 45, floor -0.35
    freelancer_vol = (occupation == "Freelancer") * rng.normal(0.0, 0.22, N)

    log_income_raw = rng.normal(0.0, 0.34, N) + occ_income_shift + experience + freelancer_vol

    # Calibrate the log-normal so mean=68,450 / std=29,800 (paper Table 4.1)
    cv_i = PAPER["income"]["std"] / PAPER["income"]["mean"]
    sigma_i = float(np.sqrt(np.log(1.0 + cv_i ** 2)))
    mu_i = float(np.log(PAPER["income"]["mean"]) - sigma_i ** 2 / 2.0)
    log_income = mu_i + sigma_i * z(log_income_raw)
    monthly_income = np.rint(np.clip(np.exp(log_income), PAPER["income"]["lo"], PAPER["income"]["hi"])).astype(np.int64)

    z_income = z(np.log(monthly_income))

    # ======================================================================
    # Step 3 - Psychometric score (0-100), normal + weak income link
    # ======================================================================
    psychometric_score = np.clip(
        58.0 + 15.5 * rng.normal(0.0, 1.0, N) + 1.5 * z_income, 3.0, 97.0
    ).round(1)
    z_psych = z(psychometric_score)

    # ======================================================================
    # Step 4 - Existing loan history (categorical)
    # ======================================================================
    # Latent "responsibility": psychometrics + income + pure heterogeneity
    responsibility = 0.45 * z_psych + 0.15 * z_income + 0.55 * rng.normal(0.0, 1.0, N)

    # Older borrowers are more likely to have borrowed before
    p_has_history = sigmoid(0.10 + 0.030 * (age - 37.6))
    has_history = rng.random(N) < p_has_history

    # Among borrowers with history: softmax over Good / Delayed / Default
    g = 0.60 + 1.10 * responsibility
    d = 0.00 + 0.20 * responsibility
    f = -1.20 - 0.80 * responsibility
    eg, ed, ef = np.exp(g), np.exp(d), np.exp(f)
    p_good, p_delayed = eg / (eg + ed + ef), ed / (eg + ed + ef)

    u = rng.random(N)
    cat = np.where(u < p_good, "Good Repayment History",
          np.where(u < p_good + p_delayed, "Delayed Repayment History", "Previous Default"))
    existing_loan_history = np.where(has_history, cat, "No Previous Loan")

    hist_eff = map_values(existing_loan_history, {k: LOAN_HISTORY[k]["hist_eff"] for k in LOAN_HISTORY})

    # ======================================================================
    # Step 5 - Debt-to-income ratio (DTI)
    # ======================================================================
    # DTI = base[history] + income-percentile effect + noise
    hist_dti_base = map_values(existing_loan_history, {k: LOAN_HISTORY[k]["dti_base"] for k in LOAN_HISTORY})
    income_pct = pd.Series(monthly_income).rank(pct=True).to_numpy()
    debt_to_income_ratio = np.clip(
        hist_dti_base + 0.055 * (1.0 - income_pct) + rng.normal(0.0, 0.09, N), 0.01, 0.92
    ).round(3)
    z_dti = z(debt_to_income_ratio)

    # ======================================================================
    # Step 6 - Loan size (PKR), the MODERATING variable
    # ======================================================================
    # Requested loan = income multiple (log-normal), adjusted by occupation
    # and DTI (heavily indebted borrowers qualify for smaller loans).
    occ_loan_adj = map_values(occupation, {o: OCCUPATIONS[o]["loan_adj"] for o in OCCUPATIONS})
    log_loan_raw = (np.log(monthly_income) + np.log(7.2)
                    + rng.normal(0.0, 0.95, N) + occ_loan_adj - 0.25 * z_dti)
    z_loan_raw = z(log_loan_raw)

    # Small micro-loan segment (~0.6%) reproduces the paper's ~50k minimum
    micro_mask = rng.random(N) < 0.006
    micro_vals = rng.uniform(50_000, 110_000, N)

    # Iteratively calibrate mu/sigma so the FINAL (clipped) loan size hits
    # mean=520,000 / std=180,000 from paper Table 4.1.
    cv_l = PAPER["loan"]["std"] / PAPER["loan"]["mean"]
    sigma_l = float(np.sqrt(np.log(1.0 + cv_l ** 2)))
    mu_l = float(np.log(PAPER["loan"]["mean"]) - sigma_l ** 2 / 2.0)
    loan = None
    for _ in range(12):
        loan = np.where(micro_mask, micro_vals, np.exp(mu_l + sigma_l * z_loan_raw))
        loan = np.clip(loan, PAPER["loan"]["lo"], PAPER["loan"]["hi"])
        m_err = (PAPER["loan"]["mean"] - loan.mean()) / PAPER["loan"]["mean"]
        s_err = (PAPER["loan"]["std"] - loan.std()) / PAPER["loan"]["std"]
        if abs(m_err) < 0.002 and abs(s_err) < 0.002:
            break
        mu_l += m_err * 0.9
        sigma_l *= (1.0 + 0.9 * s_err)
    loan_size = np.rint(loan).astype(np.int64)

    # Loan burden: requested loan as a multiple of ANNUAL income.
    # This is how loan_size moderates the effect of other characteristics.
    burden = loan_size / (monthly_income * 12.0)

    # ======================================================================
    # Step 7 - Telecom usage & mobile wallet activity (bounded scores)
    # ======================================================================
    # Beta distributions (paper's mean/std), tilted by behaviour-linked
    # covariates, re-standardized back to the paper's stats, then clipped.
    telecom_raw = (rng.beta(6.79, 4.35, N)
                   + 0.020 * z_income + 0.020 * z_psych - 0.020 * z_age)
    telecom_usage_score = np.clip(
        PAPER["telecom"]["mean"] + PAPER["telecom"]["std"] * z(telecom_raw),
        PAPER["telecom"]["lo"], PAPER["telecom"]["hi"]).round(3)
    z_telecom = z(telecom_usage_score)

    wallet_raw = (rng.beta(3.13, 2.77, N)
                  + 0.035 * z_income - 0.040 * z_age + 0.020 * z_psych)
    mobile_wallet_activity = np.clip(
        PAPER["wallet"]["mean"] + PAPER["wallet"]["std"] * z(wallet_raw),
        PAPER["wallet"]["lo"], PAPER["wallet"]["hi"]).round(3)
    z_wallet = z(mobile_wallet_activity)

    # ======================================================================
    # Step 8 - Digital purchase frequency (purchases per month)
    # ======================================================================
    # Negative-binomial counts (over-dispersed, like real purchase data),
    # driven by wallet activity, income, age and psychometrics.
    lam = np.exp(1.10 + 0.90 * z_wallet + 0.35 * z_income
                 - 0.25 * z_age + 0.15 * z_psych)
    digital_purchase_frequency = np.minimum(
        rng.negative_binomial(3.0, 3.0 / (3.0 + lam)), 45).astype(np.int64)

    # ======================================================================
    # Step 9 - Repayment score (target, continuous 0-100)
    # ======================================================================
    # Nonlinear effect of digital purchases: inverted-U peaking ~6/month
    # (zero digital footprint is mildly negative; extreme frequency
    # suggests excessive spending).
    dpf_eff = np.clip(
        -0.012 * np.abs(digital_purchase_frequency - 6.0)
        + 0.04 * np.minimum(digital_purchase_frequency, 1),
        -0.30, 0.06)

    occ_eff = map_values(occupation, {o: OCCUPATIONS[o]["score_eff"] for o in OCCUPATIONS})
    age_eff = -0.06 * ((age - 42.0) / 23.0) ** 2          # young/senior penalty

    # --- Moderation through loan burden ---
    burden_c = np.clip(burden, 0.0, 2.6)
    burden_eff = -0.50 * np.clip(burden - 0.35, 0.0, 2.6)   # big loan vs income
    relief = np.clip(burden_c - 0.8, 0.0, 1.7) / 1.7        # 0..1 for big loans

    inter_dti_burden = -0.26 * z_dti * (burden_c / 1.25)                  # DTI x burden
    inter_good_burden = 0.12 * (existing_loan_history == "Good Repayment History") * relief
    inter_default_burden = -0.12 * (existing_loan_history == "Previous Default") * relief

    z_log_loan = z(np.log(loan_size))

    latent = (0.20 * z_income                     # income capacity (+)
              - 0.15 * z_dti                      # indebtedness (-)
              + 0.45 * hist_eff                   # repayment track record (+/-)
              + 0.16 * z_telecom                  # digital stability (+)
              + 0.17 * z_wallet                   # wallet activity (+)
              + 0.16 * z_psych                    # behavioural strength (+)
              + dpf_eff                           # inverted-U digital effect
              + occ_eff                           # occupation stability
              + age_eff                           # life-cycle effect
              - 0.24 * z_log_loan                 # absolute-size friction
              + burden_eff                        # loan burden (moderator)
              + inter_dti_burden                  # interactions with burden
              + inter_good_burden
              + inter_default_burden
              + rng.normal(0.0, 0.42, N))         # unobserved factors

    repayment_score = (100.0 * sigmoid(0.58 + 1.00 * latent)).round(2)

    # ======================================================================
    # Assemble the dataframe
    # ======================================================================
    df = pd.DataFrame({
        "borrower_id": [f"PK-{i:05d}" for i in range(1, N + 1)],
        "age": age,
        "occupation": occupation,
        "monthly_income": monthly_income,
        "existing_loan_history": existing_loan_history,
        "loan_history_code": map_values(existing_loan_history,
                                        {k: LOAN_HISTORY[k]["code"] for k in LOAN_HISTORY}),
        "debt_to_income_ratio": debt_to_income_ratio,
        "loan_size": loan_size,
        "telecom_usage_score": telecom_usage_score,
        "mobile_wallet_activity": mobile_wallet_activity,
        "digital_purchase_frequency": digital_purchase_frequency,
        "psychometric_score": psychometric_score,
        # --- non-predictive demographic columns (fairness audit only) ---
        "gender": gender,
        "province": province,
        # --- target ---
        "repayment_score": repayment_score,
    })
    return df, burden


# --------------------------------------------------------------------------
# Validation report
# --------------------------------------------------------------------------
def build_report(df, burden):
    L = []  # report lines
    rs = df["repayment_score"]
    ap = L.append

    ap("=" * 78)
    ap("DATASET REPORT - Synthetic Credit Scoring Dataset (Pakistan)")
    ap("Replicates Khan et al. (2025), Table 4.1 calibration, continuous target")
    ap(f"Reproducible with random_state = {RANDOM_STATE}")
    ap("=" * 78)

    # ---------------------------------------------------------------- 1
    ap("")
    ap("1. DATASET OVERVIEW")
    ap("-" * 78)
    ap(f"Number of rows      : {len(df)}")
    ap(f"Number of columns   : {df.shape[1]}")
    ap(f"Missing values      : {int(df.isna().sum().sum())}")
    ap(f"Duplicate rows      : {int(df.duplicated().sum())} (full row, incl. borrower_id)")
    ap(f"                      {int(df.drop(columns=['borrower_id']).duplicated().sum())} (excluding borrower_id)")
    ap("")
    ap("Column roles:")
    ap("  ID          : borrower_id")
    ap("  PREDICTORS  : age, occupation, monthly_income, existing_loan_history")
    ap("                (loan_history_code = numeric encoding of it),")
    ap("                debt_to_income_ratio, loan_size, telecom_usage_score,")
    ap("                mobile_wallet_activity, digital_purchase_frequency,")
    ap("                psychometric_score")
    ap("  DEMOGRAPHIC : gender, province  (NON-predictive, fairness audit only;")
    ap("                generated independently of every other column and target)")
    ap("  TARGET      : repayment_score  (continuous, 0-100)")
    ap("")
    ap("Data types:")
    for col in df.columns:
        ap(f"  {col:<28} {str(df[col].dtype)}")

    # ---------------------------------------------------------------- 2
    ap("")
    ap("2. CALIBRATION vs PAPER (Table 4.1)")
    ap("-" * 78)
    rows = [
        ("Age (years)", df.age, "37.6 / 9.5 / 18 / 65", ".1f"),
        ("Monthly Income (PKR)", df.monthly_income, "68,450 / 29,800 / 15,000 / 250,000", ",.0f"),
        ("Loan Size (PKR)", df.loan_size, "520,000 / 180,000 / 50,000 / 1,200,000", ",.0f"),
        ("Telecom Usage Score", df.telecom_usage_score, "0.61 / 0.14 / 0.20 / 0.98", ".3f"),
        ("Mobile Wallet Activity", df.mobile_wallet_activity, "0.53 / 0.19 / 0.10 / 0.95", ".3f"),
    ]
    ap(f"{'Variable':<24}{'Paper mean/std/min/max':<38}{'Generated':<38}")
    for name, s, paper_s, fmt in rows:
        gen = (f"{format(s.mean(), fmt)} / {format(s.std(), fmt)} / "
               f"{format(s.min(), fmt)} / {format(s.max(), fmt)}")
        ap(f"{name:<24}{paper_s:<38}{gen:<38}")
    ap("(No paper statistics exist for DTI, psychometric score, digital")
    ap(" purchase frequency or the repayment score - see assumptions.)")

    # ---------------------------------------------------------------- 3
    ap("")
    ap("3. DESCRIPTIVE STATISTICS")
    ap("-" * 78)
    num_cols = ["age", "monthly_income", "debt_to_income_ratio", "loan_size",
                "telecom_usage_score", "mobile_wallet_activity",
                "digital_purchase_frequency", "psychometric_score",
                "repayment_score"]
    ap(f"{'Variable':<28}{'Mean':>12}{'Std':>12}{'Min':>12}{'Median':>12}{'Max':>12}")
    for c in num_cols:
        s = df[c]
        ap(f"{c:<28}{s.mean():>12.3f}{s.std():>12.3f}{s.min():>12.3f}"
           f"{s.median():>12.3f}{s.max():>12.3f}")

    # ---------------------------------------------------------------- 4
    ap("")
    ap("4. RELATIONSHIP ANALYSIS (correlation with repayment_score)")
    ap("-" * 78)
    corr_specs = [
        ("monthly_income", "+", 0.02, "higher income -> higher score"),
        ("debt_to_income_ratio", "-", -0.02, "higher DTI -> lower score"),
        ("telecom_usage_score", "+", 0.02, "more stable telecom -> higher score"),
        ("mobile_wallet_activity", "+", 0.02, "stronger wallet use -> higher score"),
        ("digital_purchase_frequency", "+ (weak, nonlinear)", -0.02,
         "inverted-U: moderate digital activity best"),
        ("psychometric_score", "+", 0.02, "stronger behaviour -> higher score"),
        ("loan_size", "- (weak, via burden)", -0.02,
         "large loan relative to income -> lower score"),
        ("age", "~ 0 (weak)", None, "small life-cycle effect only"),
    ]
    ap(f"{'Predictor':<28}{'Pearson r':>10}{'Spearman':>10}   {'Expected':<26}{'Verdict'}")
    for col, expected, tol, meaning in corr_specs:
        r = float(df[col].corr(rs))
        # Spearman = Pearson on ranks (avoids a scipy dependency)
        rho = float(df[col].rank().corr(rs.rank()))
        if tol is None:
            ok = abs(r) < 0.15
        else:
            ok = r > tol if expected.startswith("+") else r < tol
        ap(f"{col:<28}{r:>10.3f}{rho:>10.3f}   {expected:<26}{'PASS' if ok else 'FAIL'}")
    ap("")
    rb = float(pd.Series(burden).corr(rs))
    ap(f"Derived loan burden (loan_size / annual income) vs score: r = {rb:.3f}")
    ap("")
    ap("Key feature-feature correlations (spec section 15):")
    ap(f"  monthly_income <-> loan_size           : "
       f"{float(df.monthly_income.corr(df.loan_size)):+.3f}  (loans track income)")
    ap(f"  monthly_income <-> debt_to_income_ratio: "
       f"{float(df.monthly_income.corr(df.debt_to_income_ratio)):+.3f}  (poorer borrowers more indebted)")
    ap(f"  mobile_wallet_activity <-> digital_purchase_frequency: "
       f"{float(df.mobile_wallet_activity.corr(df.digital_purchase_frequency)):+.3f}  (wallet use drives digital spending)")
    ap(f"  loan_size <-> debt_to_income_ratio     : "
       f"{float(df.loan_size.corr(df.debt_to_income_ratio)):+.3f}  (heavily indebted qualify for smaller loans)")
    ap("Interpretations (right column) hold by construction; all learned from")
    ap("the generation mechanism documented in section 9.")

    # ---------------------------------------------------------------- 5
    ap("")
    ap("5. OCCUPATION ANALYSIS")
    ap("-" * 78)
    occ = df.groupby("occupation").agg(
        n=("borrower_id", "count"),
        mean_income=("monthly_income", "mean"),
        mean_score=("repayment_score", "mean"),
        mean_dti=("debt_to_income_ratio", "mean")).sort_values("mean_score", ascending=False)
    ap(f"{'Occupation':<20}{'Count':>7}{'Share':>8}{'Mean income':>14}{'Mean DTI':>10}{'Mean score':>12}")
    for name, row in occ.iterrows():
        ap(f"{name:<20}{int(row['n']):>7}{row['n'] / N:>8.1%}"
           f"{row['mean_income']:>14,.0f}{row['mean_dti']:>10.3f}{row['mean_score']:>12.2f}")

    # ---------------------------------------------------------------- 6
    ap("")
    ap("6. LOAN HISTORY ANALYSIS")
    ap("-" * 78)
    hist = df.groupby("existing_loan_history").agg(
        n=("borrower_id", "count"),
        mean_score=("repayment_score", "mean"),
        mean_dti=("debt_to_income_ratio", "mean")).sort_values("mean_score", ascending=False)
    ap(f"{'Category':<28}{'Count':>7}{'Share':>8}{'Mean DTI':>10}{'Mean score':>12}")
    for name, row in hist.iterrows():
        ap(f"{name:<28}{int(row['n']):>7}{row['n'] / N:>8.1%}"
           f"{row['mean_dti']:>10.3f}{row['mean_score']:>12.2f}")
    ap("Encoding: 0=No Previous Loan, 1=Good Repayment History,")
    ap("          2=Delayed Repayment History, 3=Previous Default")

    # ---------------------------------------------------------------- 7
    ap("")
    ap("7. MODERATING EFFECT OF LOAN SIZE (loan burden buckets)")
    ap("-" * 78)
    ap("Loan burden = loan_size / (12 * monthly_income). Mean repayment score")
    ap("by burden bucket, split by income half (moderation of income effect):")
    med_inc = df.monthly_income.median()
    lower = df.monthly_income.to_numpy() <= med_inc
    edges = [0.0, 0.4, 0.6, 0.8, 1.0, 1.4, np.inf]
    labels = ["< 0.40", "0.40-0.60", "0.60-0.80", "0.80-1.00", "1.00-1.40", "> 1.40"]
    idx = np.searchsorted(edges, burden, side="right") - 1
    ap(f"{'Burden bucket':<16}{'n':>6}{'Mean score':>12}{'Lower-inc half':>16}{'Upper-inc half':>16}")
    for j, lab in enumerate(labels):
        m = idx == j
        lo_s = rs.to_numpy()[m & lower].mean() if (m & lower).sum() else float("nan")
        hi_s = rs.to_numpy()[m & ~lower].mean() if (m & ~lower).sum() else float("nan")
        ap(f"{lab:<16}{int(m.sum()):>6}{rs.to_numpy()[m].mean():>12.2f}{lo_s:>16.2f}{hi_s:>16.2f}")
    ap("")
    ap("Reading: mean score falls as burden rises; the gap between income")
    ap("halves widens at high burden - exactly the moderating role of loan")
    ap("size described in the paper (Section 3.4.3).")

    # ---------------------------------------------------------------- 8
    ap("")
    ap("8. TARGET DISTRIBUTION (repayment_score)")
    ap("-" * 78)
    band_edges = [0, 20, 40, 60, 80, 100]
    band_names = ["0-20   Very low", "21-40  Low", "41-60  Moderate",
                  "61-80  High", "81-100 Very high"]
    bidx = np.digitize(rs.to_numpy(), band_edges[1:-1], right=True)
    ap(f"{'Band':<18}{'Count':>7}{'Share':>9}")
    for j, name in enumerate(band_names):
        cnt = int((bidx == j).sum())
        ap(f"{name:<18}{cnt:>7}{cnt / N:>9.1%}")
    pct_low = float((rs < 45).mean())
    ap("")
    ap(f"Share of borrowers with score < 45 (elevated risk): {pct_low:.1%}")
    ap("(Paper's default rate for reference: 22% - the low-score tail is")
    ap(" calibrated to echo that risk level.)")
    ap("")
    ap(ascii_hist(rs, bins=20, title="Repayment score distribution"))

    # ---------------------------------------------------------------- 9
    ap("")
    ap("9. GENERATION ASSUMPTIONS AND FORMULAS")
    ap("-" * 78)
    ap(assumptions_text())

    # --------------------------------------------------------------- 10
    ap("")
    ap("10. DATA QUALITY CHECKS")
    ap("-" * 78)
    checks = quality_checks(df)
    for name, ok in checks:
        ap(f"[{'PASS' if ok else 'FAIL'}] {name}")
    ap("")
    ap(f"Summary: {sum(ok for _, ok in checks)}/{len(checks)} checks passed.")

    # --------------------------------------------------------------- 11
    ap("")
    ap("11. MACHINE LEARNING READINESS")
    ap("-" * 78)
    ap("Task   : regression / continuous scoring")
    ap("Target : repayment_score (continuous, 0-100)")
    ap("Split  : none performed here; split later (e.g., 80/20 + 5-fold CV")
    ap("         as in the paper's methodology).")
    ap("Models : Linear Regression, Random Forest, XGBoost / Gradient")
    ap("         Boosting regressors; evaluate with MAE, RMSE, R^2 and")
    ap("         predicted-vs-actual correlation.")
    ap("Noise  : ~35-40% of latent variance is unobserved-factor noise, so")
    ap("         models learn real structure without unrealistic R^2.")
    ap("")
    ap("=" * 78)
    ap("END OF REPORT")
    ap("=" * 78)
    return "\n".join(L)


def quality_checks(df):
    """All data-quality requirements from the project specification."""
    return [
        ("Exactly 10,000 records", len(df) == N),
        ("Unique borrower IDs", df["borrower_id"].nunique() == N),
        ("No duplicate rows", int(df.duplicated().sum()) == 0),
        ("No missing values", int(df.isna().sum().sum()) == 0),
        ("No negative income", bool((df.monthly_income >= 0).all())),
        ("No negative loan sizes", bool((df.loan_size >= 0).all())),
        ("Age within [18, 65]", bool(df.age.between(18, 65).all())),
        ("DTI within [0, 1]", bool(df.debt_to_income_ratio.between(0, 1).all())),
        ("Telecom score within [0.20, 0.98]",
         bool(df.telecom_usage_score.between(0.20, 0.98).all())),
        ("Wallet activity within [0.10, 0.95]",
         bool(df.mobile_wallet_activity.between(0.10, 0.95).all())),
        ("Psychometric score within [0, 100]",
         bool(df.psychometric_score.between(0, 100).all())),
        ("Repayment score within [0, 100]",
         bool(df.repayment_score.between(0, 100).all())),
        ("Valid occupation categories", set(df.occupation) <= set(OCCUPATIONS)),
        ("Valid loan-history values", set(df.existing_loan_history) <= set(LOAN_HISTORY)),
    ]


def assumptions_text():
    return """(z(x) = population-standardized value; sigmoid(x) = 1/(1+e^-x))

1. Demographics
   - age ~ Normal(37.6, 9.5), clipped to [18, 65], integer.
   - occupation ~ Categorical{Salaried 22%, Self-Employed 26%,
     Business Owner 18%, Freelancer 8%, Daily Wage Worker 20%, Other 6%}.
   - gender (Male 62% / Female 38%) and province (Punjab 53% / Sindh 23% /
     KP 17% / Balochistan 7%) are generated INDEPENDENTLY of everything
     else and are NOT among the 10 predictors. They exist only for
     fairness auditing (fairness by construction).

2. Monthly income (PKR) - log-normal
   log(income) = N(mu*, sigma*) + occupation_shift + experience(age) + extra
   - occupation_shift (log scale): Business Owner +0.28, Self-Employed
     +0.06, Salaried 0.00 (reference), Freelancer -0.05, Other -0.18,
     Daily Wage Worker -0.38.
   - experience(age) = -0.025*((age-45)/10)^2, floor -0.35 (income peaks
     around age 45).
   - Freelancers receive extra volatility N(0, 0.22) (gig-income risk).
   - mu*, sigma* chosen so mean = 68,450 and std = 29,800 (paper Table
     4.1); final values clipped to [15,000, 250,000].

3. Psychometric score (0-100)
   ~ Normal(58, 15.5) + 1.5*z(log income), clipped to [3, 97].

4. Existing loan history (categorical)
   - P(has any history) = sigmoid(0.10 + 0.030*(age - 37.6)).
   - Among those with history, category ~ softmax over a latent
     responsibility factor r = 0.45*z(psych) + 0.15*z(log income)
     + 0.55*N(0,1):
       P(Good)    ~ exp(0.60 + 1.10*r)
       P(Delayed) ~ exp(0.00 + 0.20*r)
       P(Default) ~ exp(-1.20 - 0.80*r)

5. Debt-to-income ratio (0-1)
   DTI = base[history] + 0.055*(1 - income percentile) + N(0, 0.09),
   base: No Previous Loan 0.07, Good 0.15, Delayed 0.28, Default 0.38,
   clipped to [0.01, 0.92]. Lower-income and troubled-history borrowers
   carry more existing debt (as observed in microfinance portfolios).

6. Loan size (PKR) - MODERATING variable
   log(loan) = log(income) + log(7.2) + N(0, 0.95) + occupation_loan_adj
               - 0.25*z(DTI)
   - occupation_loan_adj: Business Owner +0.18, Self-Employed +0.05,
     Salaried -0.05, Freelancer -0.10, Other -0.15, Daily Wage -0.28.
   - ~0.6% of borrowers form a micro-loan segment ~ Uniform(50k, 110k),
     reproducing the paper's ~PKR 50,000 minimum.
   - mu/sigma are iteratively re-calibrated so the final clipped loan
     size has mean = 520,000 and std = 180,000 (paper Table 4.1);
     values clipped to [50,000, 1,200,000].

7. Telecom usage score (0.20-0.98) - Beta(6.79, 4.35)
   plus tilts +0.020*z(income) +0.020*z(psych) -0.020*z(age),
   re-standardized to mean 0.61 / std 0.14, clipped to [0.20, 0.98].

8. Mobile wallet activity (0.10-0.95) - Beta(3.13, 2.77)
   plus tilts +0.035*z(income) -0.040*z(age) +0.020*z(psych),
   re-standardized to mean 0.53 / std 0.19, clipped to [0.10, 0.95].

9. Digital purchase frequency (purchases/month) - negative binomial
   lambda = exp(1.10 + 0.90*z(wallet) + 0.35*z(income) - 0.25*z(age)
                + 0.15*z(psych)); count ~ NegBin(mean=lambda, dispersion 3),
   capped at 45. Correlated with wallet activity, income, age, psych.

10. Repayment score (target, 0-100) - latent index + logistic squash
    latent L =
        0.20*z(log income)                    income capacity (+)
      - 0.15*z(DTI)                           indebtedness (-)
      + 0.45*history_effect                   repayment record (+/-)
              {No: 0, Good: +0.55, Delayed: -0.60, Default: -1.00}
      + 0.16*z(telecom)                       digital stability (+)
      + 0.17*z(wallet)                        wallet activity (+)
      + 0.16*z(psychometric)                  behavioural strength (+)
      + digital_effect                        INVERTED-U, peaks ~6/month:
              -0.012*|purchases - 6| + 0.04*min(purchases, 1),
              clipped to [-0.30, +0.06]
      + occupation_effect                     Salaried +0.08, Business +0.04,
              Self-Employed 0.00, Freelancer -0.04, Other -0.06, Wage -0.10
      - 0.06*((age-42)/23)^2                  very young / senior penalty
      - 0.24*z(log loan)                      absolute-size repayment friction
              (bigger loans are harder to repay on their own; also makes loan
              size a top-ranked feature as in the paper's SHAP analysis)
      - 0.50*clip(burden - 0.35, 0, 2.6)      LOAN BURDEN (moderator),
              burden = loan_size / (12 * monthly_income)
      - 0.26*z(DTI)*clip(burden,0,2.6)/1.25   interaction: high DTI x big loan
      + 0.12*GoodHistory*relief               interaction: good record buffers
      - 0.12*DefaultHistory*relief            interaction: default amplifies
              relief = clip(burden - 0.8, 0, 1.7) / 1.7
      + N(0, 0.42)                            unobserved factors (noise)
    repayment_score = 100 * sigmoid(0.58 + 1.00*L), rounded to 2 decimals.

    Moderation examples (spec section 6):
      - High income + small loan  -> burden low  -> no penalty -> high score
      - High income + huge loan   -> moderate burden penalty -> somewhat lower
      - Low income + large loan   -> burden > 1.5 -> heavy penalty, amplified
        by high DTI and/or bad history -> substantially lower score
      - Low income + small loan   -> elevated risk (low capacity) but no
        burden penalty -> moderately low score"""


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    df, burden = generate_dataset()

    # Save the dataset
    df.to_csv(CSV_PATH, index=False)

    # Save the validation report
    report = build_report(df, burden)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")

    # Validation gate: every quality check must pass
    checks = quality_checks(df)
    failed = [name for name, ok in checks if not ok]

    # Console summary
    rs = df["repayment_score"]
    print("=" * 70)
    print(" DATASET GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f" Records           : {len(df):,}")
    print(f" Predictor features: 10 (traditional + alternative + moderator)")
    print(f" Demographics      : gender, province (non-predictive, audit only)")
    print(f" Target            : repayment_score (continuous, 0-100)")
    print(f" Target range      : [{rs.min():.2f}, {rs.max():.2f}]"
          f"  mean {rs.mean():.2f}  std {rs.std():.2f}")
    print(" Major assumptions : log-normal income; beta telecom/wallet scores;")
    print("                     negative-binomial digital purchases; loan")
    print("                     burden (loan / annual income) as moderator;")
    print("                     ~35-40% latent noise; gender & province")
    print("                     fully independent (fairness by construction)")
    print(f" Validation checks : {sum(ok for _, ok in checks)}/{len(checks)} passed"
          + ("" if not failed else f"  FAILED: {failed}"))
    print(f" Files written     : {CSV_PATH}")
    print(f"                     {REPORT_PATH}")
    print("=" * 70)

    if failed:
        raise AssertionError(f"Data-quality checks failed: {failed}")


if __name__ == "__main__":
    main()
