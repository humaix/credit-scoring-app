"""Session handling and identifier masking.

Prototype auth: random session token issued at registration or login; no
passwords. CNIC and mobile are masked everywhere they appear in responses.
"""

import secrets

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .models import Applicant, Application


def new_session_token() -> str:
    return secrets.token_hex(32)


def mask_cnic(cnic: str) -> str:
    # 35202-1234567-1 -> 35202-*******-1
    parts = cnic.split("-")
    if len(parts) == 3:
        parts[1] = "*" * len(parts[1])
        return "-".join(parts)
    return "*" * len(cnic)


def mask_mobile(mobile: str) -> str:
    # 03001234567 -> 0300****567
    if len(mobile) >= 7:
        return mobile[:4] + "****" + mobile[-3:]
    return "*" * len(mobile)


def applicant_public(applicant: Applicant) -> dict:
    return {
        "id": applicant.id,
        "full_name": applicant.full_name,
        "cnic_masked": mask_cnic(applicant.cnic),
        "mobile_masked": mask_mobile(applicant.mobile),
    }


def get_current_applicant(
    request: Request, db: Session = Depends(get_db)
) -> Applicant:
    token = request.headers.get("X-Session-Token", "")
    if not token:
        raise ApiError(401, "unauthorized", "Missing session token")
    applicant = (
        db.query(Applicant).filter(Applicant.session_token == token).first()
    )
    if applicant is None:
        raise ApiError(401, "unauthorized", "Invalid or expired session")
    return applicant


def get_owned_application(
    application_id: int, applicant: Applicant, db: Session
) -> Application:
    application = db.get(Application, application_id)
    if application is None or application.applicant_id != applicant.id:
        # 404 (not 403) so one applicant cannot probe another's ids
        raise ApiError(404, "not_found", "Application not found")
    return application
