"""SQLAlchemy ORM models — one table per product entity.

Sensitive identifiers (CNIC, mobile) are stored because the verification flow
needs them, but they are never logged, always masked in API responses, and
never sent to the ML model.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
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

    # declared applicant profile snapshot consumed by the feature builder
    age: Mapped[int] = mapped_column(Integer)
    occupation: Mapped[str] = mapped_column(String(40))
    monthly_income: Mapped[float] = mapped_column(Float)
    monthly_debt_payments: Mapped[float] = mapped_column(Float)
    existing_loan_history: Mapped[str] = mapped_column(String(40))
    requested_loan_size: Mapped[float] = mapped_column(Float)
    digital_purchase_frequency: Mapped[int] = mapped_column(Integer)

    # created -> verified -> consented -> assessed -> scored
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    applicant: Mapped["Applicant"] = relationship(back_populates="applications")
    verification: Mapped["VerificationRecord"] = relationship(
        back_populates="application", uselist=False)
    consent: Mapped["ConsentRecord"] = relationship(
        back_populates="application", uselist=False)
    questionnaire: Mapped["QuestionnaireResult"] = relationship(
        back_populates="application", uselist=False)
    assessment: Mapped["AssessmentResult"] = relationship(
        back_populates="application", uselist=False)
    reports: Mapped[list["ReportFile"]] = relationship(back_populates="application")


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
