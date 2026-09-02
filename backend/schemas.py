"""Pydantic request/response schemas — validation Layer 1 (request shape).

Category and numeric-range rules come straight from explanation_utils so the
API and the ML engine always share one source of truth.
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from explanation_utils import NUMERIC_RANGES, VALID_LOAN_HISTORY, VALID_OCCUPATIONS

CNIC_PATTERN = re.compile(r"^\d{5}-\d{7}-\d{1}$")
MOBILE_PATTERN = re.compile(r"^03\d{9}$")


def _within_model_range(key: str, value: float) -> float:
    low, high, _ = NUMERIC_RANGES[key]
    if not (low <= value <= high):
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


# --------------------------------------------------------------- requests

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    cnic: str
    mobile: str

    @field_validator("cnic")
    @classmethod
    def _valid_cnic(cls, value: str) -> str:
        if not CNIC_PATTERN.match(value):
            raise ValueError(
                "cnic must use the format XXXXX-XXXXXXX-X, e.g. 35202-1234567-1")
        return value

    @field_validator("mobile")
    @classmethod
    def _valid_mobile(cls, value: str) -> str:
        if not MOBILE_PATTERN.match(value):
            raise ValueError(
                "mobile must be an 11-digit Pakistani number starting with 03, "
                "e.g. 03001234567")
        return value


class LoginRequest(BaseModel):
    cnic: str
    mobile: str


# API field name -> model feature name (ranges come from the model's rules)
_API_TO_MODEL_FIELD = {
    "age": "age",
    "monthly_income": "monthly_income",
    "requested_loan_size": "loan_size",
    "digital_purchase_frequency": "digital_purchase_frequency",
}


class ApplicationCreate(BaseModel):
    age: int
    occupation: str
    monthly_income: float
    monthly_debt_payments: float = Field(ge=0)
    existing_loan_history: str
    requested_loan_size: float
    digital_purchase_frequency: int

    @field_validator("occupation")
    @classmethod
    def _valid_occupation(cls, value: str) -> str:
        if value not in VALID_OCCUPATIONS:
            raise ValueError(f"occupation must be one of {VALID_OCCUPATIONS}")
        return value

    @field_validator("existing_loan_history")
    @classmethod
    def _valid_history(cls, value: str) -> str:
        if value not in VALID_LOAN_HISTORY:
            raise ValueError(f"existing_loan_history must be one of {VALID_LOAN_HISTORY}")
        return value

    @field_validator("age", "monthly_income", "requested_loan_size",
                     "digital_purchase_frequency")
    @classmethod
    def _within_range(cls, value: float, info) -> float:
        return _within_model_range(_API_TO_MODEL_FIELD[info.field_name], value)

    @model_validator(mode="after")
    def _dti_feasible(self):
        if self.monthly_debt_payments > self.monthly_income:
            raise ValueError(
                "monthly_debt_payments cannot exceed monthly_income "
                "(debt-to-income ratio would exceed 1.0)")
        return self


# -------------------------------------------- verification / consent / assessment

class ApplicationRef(BaseModel):
    """Every step endpoint references the application it belongs to."""
    application_id: int


class OtpVerifyRequest(ApplicationRef):
    code: str = Field(min_length=4, max_length=8)


class ConsentGrantRequest(ApplicationRef):
    # a missing category counts as declined; the service names the
    # declined categories in the error message
    wallet_activity: bool = False
    telecom_activity: bool = False
    digital_transactions: bool = False
    previous_loan_info: bool = False


class QuestionnaireSubmit(ApplicationRef):
    answers: list[int] = Field(min_length=12, max_length=12)

    @field_validator("answers")
    @classmethod
    def _likert_range(cls, values: list[int]) -> list[int]:
        for index, value in enumerate(values):
            if not 1 <= value <= 5:
                raise ValueError(
                    f"answers[{index}] must be between 1 and 5 (Likert scale)")
        return values


# --------------------------------------------------------------- responses

class ApplicantPublic(BaseModel):
    id: int
    full_name: str
    cnic_masked: str
    mobile_masked: str


class RegisterResponse(BaseModel):
    session_token: str
    applicant: ApplicantPublic


class VerificationPublic(BaseModel):
    status: str
    provider: str
    verified_at: datetime | None = None


class ConsentPublic(BaseModel):
    wallet_activity: bool
    telecom_activity: bool
    digital_transactions: bool
    previous_loan_info: bool
    granted_at: datetime


class QuestionnairePublic(BaseModel):
    psychometric_score: float
    consistency_warnings: list[str]
    completed_at: datetime


class AssessmentPublic(BaseModel):
    repayment_score: float
    raw_score: float
    score_category: str
    explanation_source: str
    created_at: datetime


class ApplicationSummary(BaseModel):
    id: int
    status: str
    occupation: str
    requested_loan_size: float
    repayment_score: float | None = None
    score_category: str | None = None
    created_at: datetime


class ApplicationCreated(BaseModel):
    application_id: int
    status: str


class ApplicationDetail(ApplicationSummary):
    age: int
    monthly_income: float
    monthly_debt_payments: float
    existing_loan_history: str
    digital_purchase_frequency: int
    applicant: ApplicantPublic
    verification: VerificationPublic | None = None
    consent: ConsentPublic | None = None
    questionnaire: QuestionnairePublic | None = None
    assessment: AssessmentPublic | None = None


class LoginResponse(BaseModel):
    session_token: str
    applicant: ApplicantPublic
    applications: list[ApplicationSummary]


class OtpRequestResponse(BaseModel):
    status: str
    expires_in_seconds: int
    notice: str
    # present only when DEV_RETURN_OTP is enabled (demo mode)
    simulated_otp: str | None = None


class OtpVerifyResponse(BaseModel):
    status: str
    message: str | None = None
    attempts_remaining: int | None = None
    verified_at: datetime | None = None
    notice: str | None = None


class ConsentGrantResponse(BaseModel):
    status: str
    categories: list[str]
    granted_at: datetime
    notice: str


class QuestionnaireSubmitResponse(BaseModel):
    psychometric_score: float
    consistency_warnings: list[str]
    completed_at: datetime
    note: str
