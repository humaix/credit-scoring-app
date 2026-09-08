"""Database engine, session factory and schema initialisation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import config
from .models import Base

import json
from datetime import date, datetime

_kwargs = {}
if config.DATABASE_URL.startswith("sqlite"):
    # TestClient and uvicorn may hit the DB from different threads
    _kwargs["connect_args"] = {"check_same_thread": False}


def _json_serializer(obj):
    return json.dumps(
        obj,
        default=lambda o: o.isoformat() if isinstance(o, (datetime, date)) else str(o),
    )


engine = create_engine(config.DATABASE_URL, json_serializer=_json_serializer, pool_pre_ping=True, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they do not exist yet and ensure schema compatibility."""
    Base.metadata.create_all(engine)
    if config.DATABASE_URL.startswith("sqlite"):
        _migrate_sqlite()


def _migrate_sqlite() -> None:
    with engine.connect() as conn:
        # 1. Add credit_information_verification to consent_records if missing
        res = conn.exec_driver_sql("PRAGMA table_info(consent_records)").fetchall()
        cols = [r[1] for r in res]
        if cols and "credit_information_verification" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE consent_records ADD COLUMN credit_information_verification BOOLEAN NOT NULL DEFAULT 0"
            )
            conn.commit()

        # 2. Add interpretation to assessment_results if missing
        res = conn.exec_driver_sql("PRAGMA table_info(assessment_results)").fetchall()
        cols = [r[1] for r in res]
        if cols and "interpretation" not in cols:
            conn.exec_driver_sql("ALTER TABLE assessment_results ADD COLUMN interpretation TEXT")
            conn.commit()

        # 3. Check existing_loan_history in applications
        res = conn.exec_driver_sql("PRAGMA table_info(applications)").fetchall()
        app_cols = {r[1]: r for r in res}
        if "existing_loan_history" in app_cols and app_cols["existing_loan_history"][3] == 1:
            conn.exec_driver_sql("PRAGMA foreign_keys=off")
            conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS applications_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    applicant_id INTEGER NOT NULL,
                    age INTEGER NOT NULL,
                    occupation VARCHAR(40) NOT NULL,
                    monthly_income FLOAT NOT NULL,
                    monthly_debt_payments FLOAT NOT NULL,
                    existing_loan_history VARCHAR(40),
                    requested_loan_size FLOAT NOT NULL,
                    digital_purchase_frequency INTEGER NOT NULL,
                    has_bank_account BOOLEAN NOT NULL,
                    bank_name VARCHAR(100),
                    bank_account_title VARCHAR(100),
                    bank_iban VARCHAR(34),
                    wallet_provider VARCHAR(30),
                    status VARCHAR(20) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(applicant_id) REFERENCES applicants (id)
                )
            """)
            conn.exec_driver_sql("""
                INSERT INTO applications_new (
                    id, applicant_id, age, occupation, monthly_income, monthly_debt_payments,
                    existing_loan_history, requested_loan_size, digital_purchase_frequency,
                    has_bank_account, bank_name, bank_account_title, bank_iban, wallet_provider,
                    status, created_at, updated_at
                )
                SELECT 
                    id, applicant_id, age, occupation, monthly_income, monthly_debt_payments,
                    existing_loan_history, requested_loan_size, digital_purchase_frequency,
                    has_bank_account, bank_name, bank_account_title, bank_iban, wallet_provider,
                    status, created_at, updated_at
                FROM applications
            """)
            conn.exec_driver_sql("DROP TABLE applications")
            conn.exec_driver_sql("ALTER TABLE applications_new RENAME TO applications")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_applications_applicant_id ON applications (applicant_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_applications_status ON applications (status)")
            conn.exec_driver_sql("PRAGMA foreign_keys=on")
            conn.commit()


def get_db():
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
