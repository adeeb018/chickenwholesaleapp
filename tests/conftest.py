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
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

    from contextlib import contextmanager
    @contextmanager
    def test_session_scope():
        s = SessionLocal()
        try:
            yield s
            s.commit()
        except:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr("app.database.connection.get_session_factory", lambda: SessionLocal)
    monkeypatch.setattr("app.database.connection.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.database.connection.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.inventory_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.inventory_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.reconciliation_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.reconciliation_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.customer_return_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.customer_return_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.weight_loss_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.sales_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.sales_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.purchase_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.purchase_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.master_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.master_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.payment_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.payment_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.setting_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.customer_rate_adjustment_service.session_scope", test_session_scope)
    monkeypatch.setattr("app.services.report_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.services.balance_service.get_session", lambda: SessionLocal())
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: 1)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.warning", lambda *args, **kwargs: 1)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *args, **kwargs: 1)

    session = SessionLocal()
    repo_item = ItemRepository(session)
    repo_item.create(name="Broiler", code="BRL")
    repo_item.create(name="Country Chicken", code="CNT")
    session.close()

    yield
