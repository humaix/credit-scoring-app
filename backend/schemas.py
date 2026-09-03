"""Pydantic request/response schemas — validation Layer 1 (request shape).

Category and numeric-range rules come straight from explanation_utils so the
API and the ML engine always share one source of truth.
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from explanation_utils import NUMERIC_RANGES, VALID_LOAN_HISTORY, VALID_OCCUPATIONS

from .security import validate_password_policy

CNIC_PATTERN = re.compile(r"^\d{5}-\d{7}-\d{1}$")
MOBILE_PATTERN = re.compile(r"^03\d{9}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Phase 5 will build the wallet-activity score service around these providers;
# declared here so validation stays in one place
WALLET_PROVIDERS = ("JazzCash", "Easypaisa", "Other")


def _within_model_range(key: str, value: float) -> float:
    low, high, _ = NUMERIC_RANGES[key]
    if not (low <= value <= high):
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


# --------------------------------------------------------------- requests

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    cnic: str
    email: str = Field(max_length=120)
    mobile: str
    password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)
    # base64-encoded images (a data: URL prefix is tolerated and stripped)
    cnic_front_image: str = Field(min_length=32, max_length=11_000_000)
    cnic_back_image: str = Field(min_length=32, max_length=11_000_000)

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

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError(
                "email must be a valid email address, e.g. you@example.com")
        return value

    @field_validator("password")
    @classmethod
    def _valid_password(cls, value: str) -> str:
        return validate_password_policy(value)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("confirm_password must match password")
        return self


class LoginRequest(BaseModel):
    """CNIC is the primary login identifier — never the email address."""

    cnic: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("cnic")
    @classmethod
    def _valid_cnic(cls, value: str) -> str:
        if not CNIC_PATTERN.match(value):
            raise ValueError(
                "cnic must use the format XXXXX-XXXXXXX-X, e.g. 35202-1234567-1")
        return value


class ForgotPasswordRequest(BaseModel):
    cnic: str

    @field_validator("cnic")
    @classmethod
    def _valid_cnic(cls, value: str) -> str:
        if not CNIC_PATTERN.match(value):
            raise ValueError(
                "cnic must use the format XXXXX-XXXXXXX-X, e.g. 35202-1234567-1")
        return value


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def _valid_password(cls, value: str) -> str:
        return validate_password_policy(value)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("confirm_password must match new_password")
        return self


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

    # ---- Phase 2: bank-account question (asked before the financial data) --
    has_bank_account: bool
    # required when has_bank_account is true; rejected otherwise. The IBAN /
    # account number accepts a Pakistani IBAN (PK.. 26 chars) or a plain
    # account number, is normalized (spaces stripped, upper-cased) and is
    # always returned masked.
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account_title: str | None = Field(default=None, max_length=100)
    bank_iban: str | None = Field(default=None, max_length=34)
    # optional applicant-declared wallet, available on both paths (the
    # alternative-data path is wallet-first; Phase 5 builds on this)
    wallet_provider: str | None = Field(default=None, max_length=30)

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

    @field_validator("bank_name", "bank_account_title")
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("bank_iban")
    @classmethod
    def _valid_iban(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace(" ", "").strip().upper()
        if not normalized:
            return None
        # a Pakistani IBAN is 24 characters: PK + 2 check digits + 20 more
        is_iban = re.fullmatch(r"PK\d{2}[A-Z0-9]{20}", normalized)
        is_account_number = re.fullmatch(r"[A-Z0-9]{8,24}", normalized)
        if not (is_iban or is_account_number):
            raise ValueError(
                "bank_iban must be a Pakistani IBAN (PK + 24 characters) or "
                "an account number of 8-24 letters/digits")
        return normalized

    @field_validator("wallet_provider")
    @classmethod
    def _valid_wallet(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if value not in WALLET_PROVIDERS:
            raise ValueError(f"wallet_provider must be one of {WALLET_PROVIDERS}")
        return value

    @model_validator(mode="after")
    def _bank_fields_match_declaration(self):
        if self.has_bank_account:
            missing = [
                name for name, value in (
                    ("bank_name", self.bank_name),
                    ("bank_account_title", self.bank_account_title),
                    ("bank_iban", self.bank_iban),
                ) if not value
            ]
            if missing:
                raise ValueError(
                    f"bank details required when has_bank_account is true; "
                    f"missing: {', '.join(missing)}")
        elif self.bank_name or self.bank_account_title or self.bank_iban:
            raise ValueError(
                "bank details can only be provided when has_bank_account "
                "is true")
        return self

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
    # declined categories in the error message. bank_account_data is only
    # required when the application declared a bank account (Phase 2)
    wallet_activity: bool = False
    telecom_activity: bool = False
    digital_transactions: bool = False
    previous_loan_info: bool = False
    bank_account_data: bool = False


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
    email_masked: str = ""
    cnic_status: str = "pending"


class RegisterResponse(BaseModel):
    session_token: str
    applicant: ApplicantPublic
    cnic_notice: str | None = None


class LogoutResponse(BaseModel):
    status: str


class ForgotPasswordResponse(BaseModel):
    message: str
    # present only in development mode (SMTP unconfigured + DEV_SHOW_RESET_LINK)
    dev_reset_url: str | None = None
    dev_notice: str | None = None


class ResetPasswordResponse(BaseModel):
    message: str


class VerificationPublic(BaseModel):
    status: str
    provider: str
    verified_at: datetime | None = None


class ConsentPublic(BaseModel):
    wallet_activity: bool
    telecom_activity: bool
    digital_transactions: bool
    previous_loan_info: bool
    # Phase 2: true only for applications that declared a bank account and
    # consented to sharing bank/statement data
    bank_account_data: bool = False
    granted_at: datetime


class QuestionnairePublic(BaseModel):
    psychometric_score: float
    consistency_warnings: list[str]
    completed_at: datetime


class Contributor(BaseModel):
    feature: str
    value: str
    shap_value: float


class ExplanationPublic(BaseModel):
    summary: str
    positive_factors: list[str]
    negative_factors: list[str]
    overall_explanation: str
    source: str


class AssessmentPublic(BaseModel):
    # everything the results dashboard needs, exactly as persisted at scoring
    # time — the dashboard and the PDF always show identical values
    repayment_score: float
    raw_score: float
    score_category: str
    base_value: float
    positive_contributors: list[Contributor]
    negative_contributors: list[Contributor]
    all_contributions: list[Contributor]
    explanation: ExplanationPublic
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
    # ---- Phase 2: bank-account declaration -------------------------------
    # raw IBAN/account number is never exposed — only the masked form
    has_bank_account: bool = False
    bank_name: str | None = None
    bank_account_title: str | None = None
    bank_iban_masked: str | None = None
    wallet_provider: str | None = None
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


class ScoringResponse(BaseModel):
    application_id: int
    status: str
    repayment_score: float
    raw_score: float
    score_category: str
    base_value: float
    positive_contributors: list[Contributor]
    negative_contributors: list[Contributor]
    all_contributions: list[Contributor]
    explanation: ExplanationPublic
    explanation_source: str
    consistency_warnings: list[str]
    provider_note: str
    disclaimer: str
    report_filename: str
