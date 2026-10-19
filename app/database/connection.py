import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config.settings import get_database_uri, get_db_path
from app.database.base import Base
from app.database.models import (
    Item, AppSetting, CustomerRateAdjustment,
    PurchaseBatch, SaleBatchAllocation, InventoryMovement,
    DailyStockReconciliation, CustomerReturn, CustomerReturnLine
)

_engine = None
_SessionLocal = None

def _migrate_schema(engine):
    """Executes automatic schema migrations for newly added columns and tables on existing DB files."""
    try:
        with engine.connect() as conn:
            # Sales table migrations
            result = conn.exec_driver_sql("PRAGMA table_info(sales);")
            sales_cols = [row[1] for row in result.fetchall()]
            if sales_cols:
                if "discount_amount" not in sales_cols:
                    conn.exec_driver_sql("ALTER TABLE sales ADD COLUMN discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00;")
                if "box_count" not in sales_cols:
                    conn.exec_driver_sql("ALTER TABLE sales ADD COLUMN box_count INTEGER NOT NULL DEFAULT 0;")

            # Purchases table migrations
            pur_res = conn.exec_driver_sql("PRAGMA table_info(purchases);")
            pur_cols = [row[1] for row in pur_res.fetchall()]
            if pur_cols:
                if "box_count" not in pur_cols:
                    conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN box_count INTEGER NOT NULL DEFAULT 0;")
                if "gross_weight_kg" not in pur_cols:
                    conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN gross_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0.000;")
                if "box_weight_kg" not in pur_cols:
                    conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN box_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0.000;")
                if "net_weight_kg" not in pur_cols:
                    conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN net_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0.000;")
                
                # Backfill gross_weight_kg and net_weight_kg for legacy purchases
                conn.exec_driver_sql("UPDATE purchases SET gross_weight_kg = weight_kg, net_weight_kg = weight_kg WHERE gross_weight_kg = 0.000 AND weight_kg > 0;")
            
            # Backfill legacy purchases into purchase_batches and inventory_movements
            # Check if purchase_batches table exists
            table_check = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_batches';").fetchone()
            if table_check:
                purchases_without_batches = conn.exec_driver_sql("""
                    SELECT p.id, p.transaction_date, p.item_id, p.gross_weight_kg, p.box_weight_kg, p.box_count, p.net_weight_kg
                    FROM purchases p
                    LEFT JOIN purchase_batches b ON p.id = b.purchase_id
                    WHERE b.id IS NULL AND p.is_deleted = 0;
                """).fetchall()

                for row in purchases_without_batches:
                    p_id, t_date, item_id, gross, box, box_cnt, net = row
                    gross = gross or 0.0
                    box = box or 0.0
                    box_cnt = box_cnt or 0
                    net = net or 0.0
                    batch_num = f"Batch P{p_id}"
                    
                    cursor = conn.exec_driver_sql(
                        """
                        INSERT INTO purchase_batches (
                            batch_number, purchase_id, item_id, purchase_date,
                            gross_weight_kg, box_weight_kg, box_count, net_weight_kg,
                            current_stock_kg, status, is_deleted, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """,
                        (batch_num, p_id, item_id, t_date, gross, box, box_cnt, net, net)
                    )
                    batch_id = cursor.lastrowid
                    
                    conn.exec_driver_sql(
                        """
                        INSERT INTO inventory_movements (
                            batch_id, movement_type, quantity_kg, business_date,
                            reference_type, reference_id, reason, created_at, updated_at
                        ) VALUES (?, 'PURCHASE', ?, ?, 'PURCHASE', ?, 'Initial Purchase Stock Migration', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """,
                        (batch_id, net, t_date, p_id)
                    )

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
