"""Score-realism checks for the live demo app.

Pure pandas/numpy/matplotlib logic with no Streamlit imports, so it can be
tested headlessly. It answers one question: is the model's score for an
applicant plausible given the 10,000 synthetic training applicants?
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent
_EXPLAINABILITY_DIR = _PROJECT_ROOT / "explainability"
if str(_EXPLAINABILITY_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPLAINABILITY_DIR))

DATASET_PATH = _PROJECT_ROOT / "data" / "synthetic_credit_scoring_dataset.csv"

NUM_FEATURES = [
    "age", "monthly_income", "debt_to_income_ratio", "loan_size",
    "telecom_usage_score", "mobile_wallet_activity",
    "digital_purchase_frequency", "psychometric_score",
]
CAT_FEATURES = ["occupation", "existing_loan_history"]


def load_dataset():
    """The synthetic training dataset (10,000 applicants, seed 42)."""
    return pd.read_csv(DATASET_PATH)


def _numeric_distances(pool, applicant):
    """Z-scored Euclidean distance of every pool row to the applicant.

    Each numeric feature is scaled by its dataset spread first, so income
    and loan size (thousands of PKR) do not drown out the 0-1 scores.
    """
    total = np.zeros(len(pool))
    for col in NUM_FEATURES:
        values = pool[col].to_numpy(dtype=float)
        spread = values.std() or 1.0
        total += ((values - float(applicant[col])) / spread) ** 2
    return np.sqrt(total)


def nearest_neighbors(df, applicant, k=50):
    """The k training rows most similar to the applicant.

    Similarity: exact match on occupation and existing loan history, then
    the smallest z-scored Euclidean distance across the eight numeric
    features. Returns (neighbor rows, size of the same-category pool).
    """
    same_cat = (
        (df["occupation"] == applicant["occupation"])
        & (df["existing_loan_history"] == applicant["existing_loan_history"])
    )
    pool = df[same_cat] if same_cat.sum() >= k else df
    distances = _numeric_distances(pool, applicant)
    order = np.argsort(distances, kind="stable")[:k]
    return pool.iloc[order], int(same_cat.sum())


def percentile_in_dataset(df, score):
    """Share of training applicants scoring below this score."""
    return float((df["repayment_score"] < score).mean())


def neighbor_summary(neighbors):
    """Actual-score statistics of the neighbor rows."""
    scores = neighbors["repayment_score"]
    return {
        "count": int(len(scores)),
        "mean": float(scores.mean()),
        "median": float(scores.median()),
        "p10": float(scores.quantile(0.10)),
        "p90": float(scores.quantile(0.90)),
        "min": float(scores.min()),
        "max": float(scores.max()),
    }


def neighbors_histogram(neighbors, prediction, path=None):
    """Distribution of the neighbors' actual scores vs the model's estimate."""
    scores = neighbors["repayment_score"]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.hist(scores, bins=14, color="#a8c4e0", edgecolor="white")
    ax.axvline(prediction, color="#b71c1c", lw=2.2,
               label=f"model estimate for this applicant: {prediction:.1f}")
    ax.axvline(scores.mean(), color="#374151", lw=1.6, ls="--",
               label=f"similar applicants' average: {scores.mean():.1f}")
    ax.set_xlabel("Actual repayment score in the training data", fontsize=9)
    ax.set_ylabel("Applicants", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        return path
    return fig


def dataset_histogram(df, prediction, path=None):
    """Full training-data score distribution with the estimate marked."""
    scores = df["repayment_score"]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.hist(scores, bins=40, color="#a8c4e0", edgecolor="white")
    ax.axvline(prediction, color="#b71c1c", lw=2.2,
               label=f"model estimate: {prediction:.1f}")
    ax.set_xlabel("Repayment score of all 10,000 training applicants", fontsize=9)
    ax.set_ylabel("Applicants", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        return path
    return fig
