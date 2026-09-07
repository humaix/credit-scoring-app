import os
import shutil
import sqlite3

DB_PATH = "credit_scoring.db"
BACKUP_PATH = "credit_scoring.db.bak4"

if not os.path.exists(BACKUP_PATH) and os.path.exists(DB_PATH):
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Backed up {DB_PATH} to {BACKUP_PATH}")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# 1. Update applications table: make existing_loan_history nullable
cur.execute("PRAGMA table_info(applications)")
app_cols = {row[1]: row for row in cur.fetchall()}

if app_cols.get("existing_loan_history", (0, 0, 0, 0))[3] == 1:
    print("Making existing_loan_history nullable in applications...")
    cur.execute("PRAGMA foreign_keys=off")
    cur.execute("BEGIN TRANSACTION")
    
    # Create new table with existing_loan_history nullable
    cur.execute("""
        CREATE TABLE applications_new (
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
    
    cur.execute("""
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
    
    cur.execute("DROP TABLE applications")
    cur.execute("ALTER TABLE applications_new RENAME TO applications")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_applications_applicant_id ON applications (applicant_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_applications_status ON applications (status)")
    
    cur.execute("COMMIT")
    cur.execute("PRAGMA foreign_keys=on")
    print("applications table updated successfully!")

# 2. Check consent_records: add credit_information_verification if missing
cur.execute("PRAGMA table_info(consent_records)")
consent_cols = [row[1] for row in cur.fetchall()]
if "credit_information_verification" not in consent_cols:
    print("Adding credit_information_verification to consent_records...")
    cur.execute("ALTER TABLE consent_records ADD COLUMN credit_information_verification BOOLEAN NOT NULL DEFAULT 0")
    print("consent_records updated successfully!")

# 3. Check assessment_results: add interpretation if missing
cur.execute("PRAGMA table_info(assessment_results)")
assess_cols = [row[1] for row in cur.fetchall()]
if "interpretation" not in assess_cols:
    print("Adding interpretation to assessment_results...")
    cur.execute("ALTER TABLE assessment_results ADD COLUMN interpretation TEXT")
    print("assessment_results updated successfully!")

con.commit()
con.close()
print("Migration completed successfully!")
