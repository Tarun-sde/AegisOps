import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://aegisops:test@127.0.0.1:5432/aegisops")
engine_url = (
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    if "postgresql" in DATABASE_URL and "+psycopg" not in DATABASE_URL
    else DATABASE_URL
)
engine = create_engine(engine_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
