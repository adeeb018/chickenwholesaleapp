import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config.settings import get_database_uri, get_db_path
from app.database.base import Base
from app.database.models import Item, AppSetting, CustomerRateAdjustment

_engine = None
_SessionLocal = None

def _migrate_schema(engine):
    """Executes automatic schema migrations for newly added columns on existing DB files."""
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA table_info(sales);")
            columns = [row[1] for row in result.fetchall()]
            if columns and "discount_amount" not in columns:
                conn.exec_driver_sql("ALTER TABLE sales ADD COLUMN discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00;")
                conn.commit()
    except Exception as e:
        pass

def init_db(uri: str | None = None) -> None:
    """Initializes SQLite database engine, session factory, tables, and seed data."""
    global _engine, _SessionLocal
    
    db_uri = uri or get_database_uri()
    
    connect_args = {"check_same_thread": False} if db_uri.startswith("sqlite") else {}
    _engine = create_engine(db_uri, connect_args=connect_args, echo=False)
    
    if db_uri.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(bind=_engine)
    _migrate_schema(_engine)
    seed_default_items()

def get_engine():
    global _engine
    if _engine is None:
        init_db()
    return _engine

def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    return _SessionLocal

def get_session() -> Session:
    """Returns a new database session with expire_on_commit disabled."""
    factory = get_session_factory()
    session = factory()
    session.expire_on_commit = False
    return session

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def seed_default_items():
    """Seeds initial chicken types if none exist."""
    session = get_session()
    try:
        existing_count = session.query(Item).count()
        if existing_count == 0:
            defaults = [
                Item(name="Broiler", code="BRL", is_active=True),
                Item(name="Country Chicken", code="CNT", is_active=True),
                Item(name="Special Chicken", code="SPC", is_active=True),
                Item(name="Parent Chicken", code="PRN", is_active=True),
            ]
            session.add_all(defaults)
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
