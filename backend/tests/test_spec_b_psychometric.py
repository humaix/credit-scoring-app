"""Spec §18 B — Psychometric Assessment.

Scoring calculation, reverse-scored questions, normalization, minimum and
maximum scores, and consistency checks for the 12-question instrument.
"""

from backend.questionnaire import (
    CONSISTENCY_PAIRS, MAX_TOTAL, MIN_TOTAL, QUESTIONS, score_questionnaire,
)


# ------------------------------------------------------ scoring calculation

def test_scoring_calculation_for_known_answers():
    # six questions at 4, six at 2 -> oriented total depends on wording,
    # hand-computed: non-reversed contribute 4, reversed contribute 6-2=4
    answers = [4 if not q["reversed"] else 2 for q in QUESTIONS]
    oriented_total = 4 * 12  # every oriented answer is 4
    expected = (oriented_total - MIN_TOTAL) / (MAX_TOTAL - MIN_TOTAL) * 100
    score, _ = score_questionnaire(answers)
    assert score == expected


def test_neutral_answers_score_midpoint():
    # every answer 3 -> oriented 3 regardless of wording -> (36-12)/48*100
    score, _ = score_questionnaire([3] * 12)
    assert score == 50.0


# ---------------------------------------------------- reverse-scored items

def test_reverse_scored_questions_move_against_the_raw_answer():
    """Raising a reversed answer must LOWER the score; the opposite for normal."""
    base = [3] * 12
    base_score, _ = score_questionnaire(base)

    normal_index = next(i for i, q in enumerate(QUESTIONS) if not q["reversed"])
    reversed_index = next(i for i, q in enumerate(QUESTIONS) if q["reversed"])

    raised_normal = list(base)
    raised_normal[normal_index] = 5
    assert score_questionnaire(raised_normal)[0] > base_score

    raised_reversed = list(base)
    raised_reversed[reversed_index] = 5
    assert score_questionnaire(raised_reversed)[0] < base_score


def test_uniform_extreme_answers_land_at_the_midpoint():
    """Answer 5 everywhere == answer 1 everywhere after reverse scoring? No —
    straightlined answer sheets always land on the neutral 50.0; the true
    extremes require direction-aware answers (covered by the tests above)."""
    all_five, _ = score_questionnaire([5] * 12)
    all_one, _ = score_questionnaire([1] * 12)
    assert all_five == 50.0
    assert all_one == 50.0


# ------------------------------------------------------------ normalization

def test_normalization_matches_the_documented_formula():
    # oriented total of 24 (midpoint of 12..60) -> exactly 25.0
    answers = []
    for question in QUESTIONS:
        # oriented answer 2 for every question -> total 24
        answers.append(2 if not question["reversed"] else 4)
    score, _ = score_questionnaire(answers)
    assert score == 25.0


def test_minimum_score_is_zero():
    # the most negative orientation: agree with every negative statement
    answers = [1 if not q["reversed"] else 5 for q in QUESTIONS]
    score, warnings = score_questionnaire(answers)
    assert score == 0.0


def test_maximum_score_is_hundred():
    answers = [5 if not q["reversed"] else 1 for q in QUESTIONS]
    score, warnings = score_questionnaire(answers)
    assert score == 100.0


# ------------------------------------------------------- consistency checks

def test_contradictory_pair_produces_warning():
    # pair (1, 9): Q1 positive wording, Q9 negative wording.
    # Q1=5 (oriented 5) and Q9=5 (reversed -> oriented 1) point in opposite
    # directions -> the pair must be flagged.
    answers = [3] * 12
    for index, question in enumerate(QUESTIONS):
        if question["id"] in (1, 9):
            answers[index] = 5
    _, warnings = score_questionnaire(answers)
    assert any("questions 1 and 9" in w for w in warnings)


def test_consistent_answers_produce_no_warnings():
    # neutral answers can never differ by >= 3 after orientation
    _, warnings = score_questionnaire([3] * 12)
    assert warnings == []


def test_all_consistency_pairs_can_fire():
    """Straightlining (the same raw answer everywhere) trips every pair —
    the instrument's balanced wording doing its job; never a rejection."""
    _, warnings = score_questionnaire([1] * 12)
    assert len(warnings) == len(CONSISTENCY_PAIRS)


# ------------------------------------------------------------- API surface

def test_questionnaire_api_score_and_resubmit(client):
    from backend.tests.flow import MODERATE, full_flow, likert_answers

    headers, application_id = full_flow(client, MODERATE, likert_answers("high"))
    # the flow already submitted the high orientation; resubmission is rejected
    response = client.post("/api/assessment/psychometric",
                           json={"application_id": application_id,
                                 "answers": likert_answers("low")},
                           headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "assessment_already_completed"


def test_questions_endpoint_exposes_twelve_balanced_questions(client):
    from backend.questionnaire import questions_public

    body = questions_public()
    assert len(body["questions"]) == 12
    assert len(body["scale"]) == 5
    # reversed flags are internal and must not leak to the UI payload
    assert all("reversed" not in q for q in body["questions"])
    # dimensions cover the four documented areas
    dimensions = {q["dimension"] for q in body["questions"]}
    assert dimensions == {
        "Financial Discipline", "Repayment Responsibility",
        "Spending Control", "Financial Planning",
    }
