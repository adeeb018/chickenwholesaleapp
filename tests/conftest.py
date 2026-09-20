import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from app.database.connection import init_db
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.provider_repository import ProviderRepository
from app.database.repositories.item_repository import ItemRepository

@pytest.fixture(autouse=True)
def setup_in_memory_db(monkeypatch):
    """
    Sets up an isolated in-memory SQLite database for every test.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

    monkeypatch.setattr("app.database.connection.get_session_factory", lambda: SessionLocal)
    monkeypatch.setattr("app.database.connection.get_session", lambda: SessionLocal())

    session = SessionLocal()
    repo_item = ItemRepository(session)
    repo_item.create(name="Broiler", code="BRL")
    repo_item.create(name="Country Chicken", code="CNT")
    session.close()

    yield
