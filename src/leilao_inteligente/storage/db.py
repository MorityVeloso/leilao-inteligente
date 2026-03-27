"""Engine e sessao do banco de dados."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from leilao_inteligente.config import get_settings
from leilao_inteligente.models.database import Base


_engine = None
_SessionLocal = None


def get_engine():
    """Retorna engine do SQLAlchemy (singleton)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        )
    return _engine


def get_session() -> Session:
    """Retorna uma nova sessao do banco."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db() -> None:
    """Cria todas as tabelas no banco."""
    engine = get_engine()
    Base.metadata.create_all(engine)
