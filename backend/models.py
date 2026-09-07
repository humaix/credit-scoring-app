"""SQLAlchemy ORM models — one table per product entity.

Sensitive identifiers (CNIC, mobile) are stored because the verification flow
needs them, but they are never logged, always masked in API responses, and
never sent to the ML model.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    # naive UTC — SQLite datetimes round-trip without timezone info
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    cnic: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    mobile: Mapped[str] = mapped_column(String(20))
    session_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # ---- Phase 1 authentication -------------------------------------------
    # email is nullable only so pre-existing demo databases keep loading;
    # every new registration requires it (password-recovery target)
    email: Mapped[str | None] = mapped_column(
        String(120), unique=True, index=True, nullable=True)
    # bcrypt hash — the plain-text password is never stored or logged
    password_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # captured CNIC documents (server-generated filenames under uploads/cnic/)
    cnic_front_filename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cnic_back_filename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # pending | prototype_verified — honest status: format + image checks
    # passed; no NADRA verification and no OCR comparison is performed
    cnic_status: Mapped[str] = mapped_column(String(30), default="pending")

    applications: Mapped[list["Application"]] = relationship(back_populates="applicant")
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="applicant", cascade="all, delete-orphan")


class PasswordResetToken(Base):
    """Single-use, expiring password-reset token (hash only, never raw)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    applicant: Mapped["Applicant"] = relationship(back_populates="reset_tokens")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id"), index=True)

    # declared applicant profile snapshot consumed by the feature builder;
    # loan history is NOT declared by the applicant any more — it is derived
    # from the credit-information verification step and copied here when that
    # step runs (nullable until then)
    age: Mapped[int] = mapped_column(Integer)
    occupation: Mapped[str] = mapped_column(String(40))
    monthly_income: Mapped[float] = mapped_column(Float)
    monthly_debt_payments: Mapped[float] = mapped_column(Float)
    existing_loan_history: Mapped[str | None] = mapped_column(
        String(40), nullable=True)
    requested_loan_size: Mapped[float] = mapped_column(Float)
    digital_purchase_frequency: Mapped[int] = mapped_column(Integer)

    # ---- Phase 2 bank-account question -------------------------------------
    # asked before the financial data; the answer steers the rest of the flow
    # (bank details + bank-data consent only exist for account holders)
    has_bank_account: Mapped[bool] = mapped_column(Boolean, default=False)
    # populated only when has_bank_account is true; IBAN/account number is
    # stored normalized and always returned masked (see auth.mask_iban)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_account_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    # optional applicant-declared wallet (JazzCash / Easypaisa / Other)
    wallet_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # created -> verified -> consented -> assessed -> scored
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    applicant: Mapped["Applicant"] = relationship(back_populates="applications")
    verification: Mapped["VerificationRecord"] = relationship(
        back_populates="application", uselist=False)
    employment: Mapped["EmploymentVerification"] = relationship(
        back_populates="application", uselist=False)
    credit_verification: Mapped["CreditVerification"] = relationship(
        back_populates="application", uselist=False)
    consent: Mapped["ConsentRecord"] = relationship(
        back_populates="application", uselist=False)
    questionnaire: Mapped["QuestionnaireResult"] = relationship(
        back_populates="application", uselist=False)
    assessment: Mapped["AssessmentResult"] = relationship(
        back_populates="application", uselist=False)
    reports: Mapped[list["ReportFile"]] = relationship(back_populates="application")


class EmploymentVerification(Base):
    """Prototype employment / financial document verification (Phase 3).

    One record per application. Without OCR or provider integrations the
    honest reachable statuses are needs_review (document captured and
    quality-checked, pending provider verification) and not_required
    (occupation without an applicable document). data_matched /
    could_not_verify stay in the vocabulary for a future authorized
    provider but are never produced in this prototype.
    """

    __tablename__ = "employment_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    # snapshot of the occupation the checks ran against
    occupation: Mapped[str] = mapped_column(String(40))
    # salary_slip | bank_statement | not_required
    doc_type: Mapped[str] = mapped_column(String(20))
    employer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # income declared in the employment section — the monthly salary for
    # salaried applicants, the re-confirmed monthly income for the business
    # branch; compared against the application's monthly income as a
    # prototype consistency check
    declared_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    # server-generated filename under uploads/employment/applicant_<id>/
    filename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # needs_review | not_required
    status: Mapped[str] = mapped_column(String(20))
    # the prototype checks performed, exactly as returned to the applicant
    checks: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="employment")


class CreditVerification(Base):
    """Credit-information verification record (spec task, section 5-7).

    One record per application. The PROTOTYPE provider is a clearly labelled
    mock (MockCreditVerificationService) — no eCIB or SBP-licensed bureau is
    contacted. The stored provider name identifies which service produced the
    record, so a real authorized provider can replace the mock later without
    touching the scoring flow. The derived loan-history category is computed
    deterministically by derive_loan_history() — never by the LLM.
    """

    __tablename__ = "credit_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    # identifies the verification source ("mock" today, a licensed bureau
    # name once a real integration exists) — always shown with the demo label
    provider: Mapped[str] = mapped_column(String(30), default="mock")
    # the six mock credit-information fields (spec section 6)
    has_previous_loan: Mapped[bool] = mapped_column(Boolean)
    has_credit_card: Mapped[bool] = mapped_column(Boolean)
    total_outstanding_amount: Mapped[float] = mapped_column(Float)
    installments_paid_on_time: Mapped[int] = mapped_column(Integer)
    has_overdue_or_default: Mapped[bool] = mapped_column(Boolean)
    total_existing_debt: Mapped[float] = mapped_column(Float)
    # deterministic mapping result — one of the model's four categories
    derived_loan_history: Mapped[str] = mapped_column(String(40))
    # flagged when the six fields contradict each other; the record is kept
    # for review but never silently mapped to a misleading category
    inconsistent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(
        back_populates="credit_verification")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock")
    # pending | verified | failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    otp_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="verification")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    wallet_activity: Mapped[bool] = mapped_column(default=False)
    telecom_activity: Mapped[bool] = mapped_column(default=False)
    digital_transactions: Mapped[bool] = mapped_column(default=False)
    previous_loan_info: Mapped[bool] = mapped_column(default=False)
    # credit-information verification consent (spec section 4): authorizes
    # obtaining the applicant's credit information from SBP eCIB / an
    # SBP-licensed bureau. Required before the verification step runs.
    credit_information_verification: Mapped[bool] = mapped_column(default=False)
    # Phase 2: only meaningful (and only required) when the application
    # declared a bank account; False for alternative-data-only applications
    bank_account_data: Mapped[bool] = mapped_column(default=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="consent")


class QuestionnaireResult(Base):
    __tablename__ = "questionnaire_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    answers: Mapped[list] = mapped_column(JSON)  # 12 Likert values, 1-5
    psychometric_score: Mapped[float] = mapped_column(Float)
    consistency_warnings: Mapped[list] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="questionnaire")


class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True, unique=True)
    repayment_score: Mapped[float] = mapped_column(Float)
    raw_score: Mapped[float] = mapped_column(Float)
    score_category: Mapped[str] = mapped_column(String(20))
    base_value: Mapped[float] = mapped_column(Float)
    positive_contributors: Mapped[list] = mapped_column(JSON)
    negative_contributors: Mapped[list] = mapped_column(JSON)
    all_contributions: Mapped[list] = mapped_column(JSON)
    # the ten validated model inputs, kept so the PDF can be re-rendered
    applicant_features: Mapped[dict] = mapped_column(JSON)
    # applicant-facing interpretation blocks, built once at scoring time so
    # the dashboard, the detail API and a re-rendered PDF always agree
    interpretation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[dict] = mapped_column(JSON)
    explanation_source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="assessment")


class ReportFile(Base):
    __tablename__ = "report_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_results.id"), index=True)
    filename: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="reports")
