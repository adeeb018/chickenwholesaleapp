import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from app.database.connection import init_db
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.provider_repository import ProviderRepository
import os
from PySide6.QtWidgets import QApplication
from app.database.repositories.item_repository import ItemRepository

os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app

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
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: 1)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.warning", lambda *args, **kwargs: 1)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *args, **kwargs: 1)

    session = SessionLocal()
    repo_item = ItemRepository(session)
    repo_item.create(name="Broiler", code="BRL")
    repo_item.create(name="Country Chicken", code="CNT")
    session.close()

    yield
