from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.utils.config import settings

# Handle thread-concurrency arguments for SQLite vs PostgreSQL
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Connection pool engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Proactively ping the DB before executing to catch stale connections
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base model class
Base = declarative_base()


def get_db():
    """Dependency helper yielding an isolated database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
