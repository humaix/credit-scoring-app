"""Registration and login endpoints (prototype session auth)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import applicant_public, new_session_token
from ..db import get_db
from ..errors import ApiError
from ..models import Applicant
from ..schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Applicant).filter(Applicant.cnic == payload.cnic).first()
    if existing is not None:
        raise ApiError(
            409, "already_registered",
            "An applicant with this CNIC is already registered - log in instead")

    applicant = Applicant(
        full_name=payload.full_name.strip(),
        cnic=payload.cnic,
        mobile=payload.mobile,
        session_token=new_session_token(),
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)
    return RegisterResponse(
        session_token=applicant.session_token,
        applicant=applicant_public(applicant),  # type: ignore[arg-type]
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    applicant = db.query(Applicant).filter(Applicant.cnic == payload.cnic).first()
    if applicant is None or applicant.mobile != payload.mobile:
        raise ApiError(401, "invalid_credentials", "CNIC and mobile do not match")

    applications = sorted(applicant.applications, key=lambda a: a.created_at,
                          reverse=True)
    return LoginResponse(
        session_token=applicant.session_token,
        applicant=applicant_public(applicant),  # type: ignore[arg-type]
        applications=[
            {
                "id": a.id,
                "status": a.status,
                "occupation": a.occupation,
                "requested_loan_size": a.requested_loan_size,
                "repayment_score": a.assessment.repayment_score if a.assessment else None,
                "score_category": a.assessment.score_category if a.assessment else None,
                "created_at": a.created_at,
            }
            for a in applications
        ],
    )
