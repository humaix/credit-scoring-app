"""Database engine, session factory and schema initialisation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import config
from .models import Base

_kwargs = {}
if config.DATABASE_URL.startswith("sqlite"):
    # TestClient and uvicorn may hit the DB from different threads
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(config.DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    Base.metadata.create_all(engine)


def get_db():
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
