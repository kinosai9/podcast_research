from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from podcast_research.config import DB_PATH
from podcast_research.db.models import Base

_engine = None
_SessionLocal = None


def init_engine(db_path: str | None = None) -> None:
    global _engine, _SessionLocal
    path = db_path or str(DB_PATH)
    _engine = create_engine(f"sqlite:///{path}", echo=False)
    _SessionLocal = sessionmaker(bind=_engine)


def init_db(db_path: str | None = None) -> None:
    if _engine is None:
        init_engine(db_path)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal()