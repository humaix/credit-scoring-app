"""Financial Behavior Assessment — produces the psychometric_score feature.

PROTOTYPE INSTRUMENT: these questions demonstrate a financial-behaviour
assessment; this is NOT a scientifically validated psychometric instrument.

12 questions across four dimensions (Financial Discipline, Repayment
Responsibility, Spending Control, Financial Planning), 5-point Likert scale,
balanced positive and negative wording. Negative questions are reverse
scored (answer 1..5 -> oriented 5..1). The oriented total (12..60) is
normalised to the model's psychometric_score scale: 0-100 — verified against
the training dataset, whose psychometric_score was generated on a 0-100
scale (observed range 3.1-97.0).
"""

from sqlalchemy.orm import Session

from .errors import ApiError
from .flow import STEP_ORDER
from .models import (
    Application, CreditVerification, QuestionnaireResult,
)

LIKERT_LABELS = [
    "Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree",
]

QUESTIONS = [
    {"id": 1, "dimension": "Financial Discipline",
     "text": "I keep money aside for loan instalments as soon as I receive income.",
     "reversed": False},
    {"id": 2, "dimension": "Financial Discipline",
     "text": "I often spend my savings before the end of the month.",
     "reversed": True},
    {"id": 3, "dimension": "Financial Discipline",
     "text": "I rarely keep track of where my money goes.",
     "reversed": True},
    {"id": 4, "dimension": "Repayment Responsibility",
     "text": "When I owe money, I make payments on time even when it is difficult.",
     "reversed": False},
    {"id": 5, "dimension": "Repayment Responsibility",
     "text": "I have borrowed from one person to repay another.",
     "reversed": True},
    {"id": 6, "dimension": "Repayment Responsibility",
     "text": "I keep a record of what I owe and when each payment is due.",
     "reversed": False},
    {"id": 7, "dimension": "Spending Control",
     "text": "I buy things on impulse even when money is tight.",
     "reversed": True},
    {"id": 8, "dimension": "Spending Control",
     "text": "Before making a large purchase, I compare prices and think it over.",
     "reversed": False},
    {"id": 9, "dimension": "Spending Control",
     "text": "I often run out of money before my next income arrives.",
     "reversed": True},
    {"id": 10, "dimension": "Financial Planning",
     "text": "I plan ahead for large expenses such as school fees or repairs.",
     "reversed": False},
    {"id": 11, "dimension": "Financial Planning",
     "text": "I keep some money aside for emergencies.",
     "reversed": False},
    {"id": 12, "dimension": "Financial Planning",
     "text": "I usually make financial decisions without thinking about the future.",
     "reversed": True},
]

# logically related pairs used only for assessment-quality warnings
CONSISTENCY_PAIRS = [(1, 9), (2, 10), (3, 8), (4, 5), (6, 12), (7, 11)]

MIN_TOTAL = len(QUESTIONS)          # 12
MAX_TOTAL = len(QUESTIONS) * 5      # 60

ASSESSMENT_NOTE = (
    "Prototype financial-behaviour assessment - not a scientifically "
    "validated psychometric instrument. Consistency warnings are "
    "assessment-quality indicators only; they never reject an applicant "
    "and never change the score."
)


def score_questionnaire(answers: list) -> tuple:
    """Return (psychometric_score 0-100, consistency warnings)."""
    oriented = [
        (6 - answer) if question["reversed"] else answer
        for question, answer in zip(QUESTIONS, answers)
    ]
    total = sum(oriented)
    psychometric = round((total - MIN_TOTAL) / (MAX_TOTAL - MIN_TOTAL) * 100.0, 1)

    by_id = {q["id"]: value for q, value in zip(QUESTIONS, oriented)}
    warnings = []
    for first, second in CONSISTENCY_PAIRS:
        if abs(by_id[first] - by_id[second]) >= 3:
            warnings.append(
                f"Answers to questions {first} and {second} point in "
                "different directions - please review.")
    return psychometric, warnings


def questions_public() -> dict:
    """Static question set for the UI (reversed flags stay internal)."""
    return {
        "scale": LIKERT_LABELS,
        "note": ASSESSMENT_NOTE,
        "questions": [
            {"id": q["id"], "dimension": q["dimension"], "text": q["text"]}
            for q in QUESTIONS
        ],
    }


def save_questionnaire(db: Session, application: Application, answers: list) -> dict:
    """Score, persist and advance the application to 'assessed'."""
    existing = (
        db.query(QuestionnaireResult)
        .filter(QuestionnaireResult.application_id == application.id)
        .first()
    )
    if existing is not None:
        # duplicate check first (same ordering as grant_consent) so a
        # resubmission after completion reports what actually happened
        raise ApiError(409, "assessment_already_completed",
                       "The financial behaviour assessment is already completed")

    if application.status != "consented":
        raise ApiError(
            409, "invalid_state",
            f"Application is '{application.status}'; expected step order: {STEP_ORDER}")

    # the credit-information verification is a sub-step that happens while
    # the application is 'consented' and must be completed before the
    # questionnaire — it supplies the loan-history feature the model needs
    verification = (
        db.query(CreditVerification)
        .filter(CreditVerification.application_id == application.id)
        .first()
    )
    if verification is None:
        raise ApiError(
            409, "credit_verification_required",
            "Complete the credit information verification step before "
            "starting the financial behaviour assessment")

    psychometric, warnings = score_questionnaire(answers)
    record = QuestionnaireResult(
        application_id=application.id,
        answers=list(answers),
        psychometric_score=psychometric,
        consistency_warnings=warnings,
    )
    db.add(record)
    application.status = "assessed"
    db.commit()
    return {
        "psychometric_score": psychometric,
        "consistency_warnings": warnings,
        "completed_at": record.completed_at,
        "note": ASSESSMENT_NOTE,
    }
