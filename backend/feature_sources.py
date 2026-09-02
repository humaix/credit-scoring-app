"""Feature-source mapping — where every model feature comes from (spec §8).

Internal documentation surfaced via /api/meta/feature-sources so reviewers
and the UI can show exactly what data is used and how it is obtained.
"""

FEATURE_SOURCES = {
    "age": {
        "label": "Age",
        "source": "identity_information",
        "description": "Declared during the loan application; part of the "
                       "identity information.",
    },
    "occupation": {
        "label": "Occupation",
        "source": "applicant_declaration",
        "description": "Declared by the applicant.",
    },
    "monthly_income": {
        "label": "Monthly Income",
        "source": "applicant_declaration",
        "description": "Declared monthly income; would be verified against a "
                       "financial source in production.",
    },
    "existing_loan_history": {
        "label": "Existing Loan History",
        "source": "applicant_declaration",
        "description": "Declared repayment history; a credit-provider "
                       "integration would verify it in production.",
    },
    "debt_to_income_ratio": {
        "label": "Debt-to-Income Ratio",
        "source": "derived",
        "description": "Derived: monthly debt payments divided by monthly "
                       "income.",
    },
    "telecom_usage_score": {
        "label": "Telecom Usage Score",
        "source": "mock_telecom_integration",
        "description": "Simulated telecom provider summary (clearly labelled "
                       "mock; no real operator is contacted). Requires "
                       "telecom activity consent.",
    },
    "mobile_wallet_activity": {
        "label": "Mobile Wallet Activity",
        "source": "mock_wallet_integration",
        "description": "Simulated wallet provider summary (clearly labelled "
                       "mock; no real wallet provider is contacted). "
                       "Requires wallet activity consent.",
    },
    "digital_purchase_frequency": {
        "label": "Digital Purchase Frequency",
        "source": "declared_digital_activity",
        "description": "Declared digital purchases per month; requires "
                       "digital transactions consent.",
    },
    "psychometric_score": {
        "label": "Psychometric Score",
        "source": "financial_behavior_assessment",
        "description": "Produced by the 12-question Financial Behavior "
                       "Assessment (prototype instrument).",
    },
    "loan_size": {
        "label": "Loan Size",
        "source": "requested_loan_amount",
        "description": "The requested loan amount.",
    },
}


def feature_sources_public() -> dict:
    return {"features": FEATURE_SOURCES}
