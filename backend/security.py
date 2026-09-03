"""Password hashing and policy (Phase 1 authentication).

Passwords are hashed with bcrypt (adaptive, salted, industry standard); the
plain-text password is never stored, logged or returned. Unknown-CNIC login
attempts still run a dummy verification so response timing does not reveal
whether an account exists.
"""

import re
import secrets

import bcrypt

# OWASP-recommended work factor for bcrypt
BCRYPT_ROUNDS = 12

MIN_PASSWORD_LENGTH = 8
_PASSWORD_RULES = (
    (lambda p: len(p) >= MIN_PASSWORD_LENGTH,
     f"password must be at least {MIN_PASSWORD_LENGTH} characters long"),
    (lambda p: re.search(r"[A-Za-z]", p) is not None,
     "password must contain at least one letter"),
    (lambda p: re.search(r"\d", p) is not None,
     "password must contain at least one digit"),
)

# module-level hash of random bytes: used to equalize the cost of rejected
# login attempts for CNICs that do not exist
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(32),
                            bcrypt.gensalt(rounds=BCRYPT_ROUNDS))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"),
                              password_hash.encode("ascii"))
    except ValueError:
        # a malformed stored hash never crashes the login path
        return False


def dummy_verify(password: str) -> None:
    """Burn the same CPU time as a real check, for CNICs that don't exist."""
    try:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
    except ValueError:  # pragma: no cover - defensive
        pass


def validate_password_policy(password: str) -> str:
    """Raise ValueError with a user-readable reason if the password is weak."""
    for rule, message in _PASSWORD_RULES:
        if not rule(password):
            raise ValueError(message)
    return password


def new_reset_token() -> tuple:
    """Return (raw token for the reset link, sha256 hex for storage).

    Only the hash is persisted — a database leak must not yield usable
    reset links, and the token itself never contains the password.
    """
    raw = secrets.token_urlsafe(32)
    import hashlib
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_reset_token(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
