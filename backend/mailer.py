"""Password-reset email delivery (Phase 1).

Real SMTP sending when SMTP_HOST is configured; otherwise the caller falls
back to the clearly-labelled development link (config.DEV_SHOW_RESET_LINK).
Credentials come only from environment variables — never from the code, and
never logged.
"""

import logging
import smtplib
from email.mime.text import MIMEText

from . import config

logger = logging.getLogger(__name__)

EMAIL_SUBJECT = "RoshanScore — password reset"

EMAIL_BODY = """\
Someone requested a password reset for your RoshanScore account.

Open this link to set a new password (valid for {ttl} minutes):

{url}

If you did not request this, you can ignore this email — your password
will not change. For your security, this link can only be used once.
"""


def smtp_configured() -> bool:
    return bool(config.SMTP_HOST)


def send_reset_email(to_email: str, reset_url: str) -> bool:
    """Send the reset email; returns False (and logs a warning) on failure.

    Failures never change the API response — the forgot-password endpoint
    must not leak whether an account exists or whether delivery succeeded.
    """
    message = MIMEText(EMAIL_BODY.format(
        ttl=config.RESET_TOKEN_TTL_MINUTES, url=reset_url), "plain", "utf-8")
    message["Subject"] = EMAIL_SUBJECT
    message["From"] = config.SMTP_FROM
    message["To"] = to_email
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        logger.warning("password-reset email could not be sent "
                       "(SMTP delivery failed)")
        return False
