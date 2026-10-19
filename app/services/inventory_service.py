from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session, session_scope
from app.database.models import (
    PurchaseBatch, SaleBatchAllocation, InventoryMovement,
    DailyStockReconciliation, CustomerReturnLine, Purchase, Sale, Item
)
from app.utils.decimal_utils import round_weight, to_decimal, format_weight

class InventoryService:
    @staticmethod
    def get_next_batch_name(session: Session, purchase_date: Optional[date] = None) -> str:
        """
        Generates human-readable batch numbers like 'Batch A', 'Batch B', 'Batch C', etc.
        Ensures uniqueness across all batches.
        """
        existing = session.query(PurchaseBatch.batch_number).all()
        existing_names = {r[0] for r in existing}

        for i in range(26):
            candidate = f"Batch {chr(65 + i)}"
            if candidate not in existing_names:
                return candidate

        # If A-Z are used, try Batch A1, B1, C1...
        for num in range(1, 1000):
            for i in range(26):
                candidate = f"Batch {chr(65 + i)}{num}"
                if candidate not in existing_names:
                    return candidate

        return f"Batch-{int(datetime.now(timezone.utc).timestamp())}"

    @staticmethod
    def create_batch(
        session: Session,
        purchase_id: Optional[int],
        item_id: int,
        purchase_date: date,
        gross_weight_kg: any,
        box_weight_kg: any = 0.000,
        box_count: int = 0,
        batch_number: Optional[str] = None
    ) -> PurchaseBatch:
        gross = round_weight(gross_weight_kg)
        box = round_weight(box_weight_kg)
        box_cnt = int(box_count or 0)

        if gross <= 0:
            raise ValueError("Gross weight must be greater than 0.")
        if box < 0:
            raise ValueError("Box weight cannot be negative.")
        if box > gross:
            raise ValueError("Box weight cannot exceed gross weight.")

        net = round_weight(gross - box)
        if net <= 0:
            raise ValueError("Net weight must be greater than 0.")

        if not batch_number or not batch_number.strip():
            b_name = InventoryService.get_next_batch_name(session, purchase_date)
        else:
            b_name = batch_number.strip()
            # Verify uniqueness
            existing = session.query(PurchaseBatch).filter(PurchaseBatch.batch_number == b_name).first()
            if existing:
                raise ValueError(f"Batch number '{b_name}' already exists. Please choose a unique batch name.")

        batch = PurchaseBatch(
            batch_number=b_name,
            purchase_id=purchase_id,
            item_id=item_id,
            purchase_date=purchase_date,
            gross_weight_kg=gross,
            box_weight_kg=box,
            box_count=box_cnt,
            net_weight_kg=net,
            current_stock_kg=net,
            status="ACTIVE"
        )
        session.add(batch)
        session.flush()

        # Add initial PURCHASE movement in inventory ledger
        movement = InventoryMovement(
            batch_id=batch.id,
            movement_type="PURCHASE",
            quantity_kg=net,
            business_date=purchase_date,
            reference_type="PURCHASE",
            reference_id=purchase_id,
            reason="Purchase stock intake"
        )
        session.add(movement)
        session.flush()

        return batch

    @staticmethod
    def record_movement(
        session: Session,
        batch_id: int,
        movement_type: str,
        quantity_kg: any,
        business_date: date,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> InventoryMovement:
        qty = round_weight(quantity_kg)
        batch = session.query(PurchaseBatch).filter(PurchaseBatch.id == batch_id).with_for_update(nowait=False).first()
        if not batch:
            raise ValueError(f"Batch with ID {batch_id} not found.")

        new_stock = round_weight(batch.current_stock_kg + qty)
        if new_stock < 0:
            raise ValueError(
                f"Negative stock prevented for batch {batch.batch_number}: "
                f"Current stock {batch.current_stock_kg} KG, requested change {qty} KG."
            )

        batch.current_stock_kg = new_stock
        if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
            batch.status = "DEPLETED"
        elif batch.current_stock_kg > 0 and batch.status == "DEPLETED":
            batch.status = "ACTIVE"

        movement = InventoryMovement(
            batch_id=batch_id,
            movement_type=movement_type.upper(),
            quantity_kg=qty,
            business_date=business_date,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
            notes=notes
        )
        session.add(movement)
        session.flush()
        return movement

    @staticmethod
    def calculate_batch_stock(session: Session, batch_id: int) -> Decimal:
        """Sums all ledger movements for this batch to get the true sellable stock."""
        movements = session.query(InventoryMovement).filter(InventoryMovement.batch_id == batch_id).all()
        total = sum((m.quantity_kg for m in movements), Decimal("0.000"))
        return round_weight(total)

    @staticmethod
    def verify_and_sync_batch_stock(session: Session, batch_id: int) -> Decimal:
        """Verifies that cached current_stock_kg equals sum of ledger movements."""
        true_stock = InventoryService.calculate_batch_stock(session, batch_id)
        batch = session.query(PurchaseBatch).filter(PurchaseBatch.id == batch_id).first()
        if batch:
            if batch.current_stock_kg != true_stock:
                batch.current_stock_kg = true_stock
                if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
                    batch.status = "DEPLETED"
                elif batch.current_stock_kg > 0 and batch.status == "DEPLETED":
                    batch.status = "ACTIVE"
                session.flush()
        return true_stock

    @staticmethod
    def get_batches(
        status: Optional[str] = None,
        item_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_closed: bool = True
    ) -> List[PurchaseBatch]:
        session = get_session()
        try:
            query = (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(PurchaseBatch.is_deleted == False)
            )
            if status:
                query = query.filter(PurchaseBatch.status == status.upper())
            elif not include_closed:
                query = query.filter(PurchaseBatch.status != "CLOSED")
            if item_id:
                query = query.filter(PurchaseBatch.item_id == item_id)
            if start_date:
                query = query.filter(PurchaseBatch.purchase_date >= start_date)
            if end_date:
                query = query.filter(PurchaseBatch.purchase_date <= end_date)

            return query.order_by(PurchaseBatch.purchase_date.desc(), PurchaseBatch.id.desc()).all()
        finally:
            session.close()

    @staticmethod
    def get_sellable_batches(item_id: Optional[int] = None) -> List[PurchaseBatch]:
        """Returns all ACTIVE batches with available stock > 0."""
        session = get_session()
        try:
            query = (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(
                    PurchaseBatch.is_deleted == False,
                    PurchaseBatch.status == "ACTIVE",
                    PurchaseBatch.current_stock_kg > 0
                )
            )
            if item_id:
                query = query.filter(PurchaseBatch.item_id == item_id)
            return query.order_by(PurchaseBatch.purchase_date.asc(), PurchaseBatch.id.asc()).all()
        finally:
            session.close()

    @staticmethod
    def get_batch_by_id(batch_id: int) -> Optional[PurchaseBatch]:
        session = get_session()
        try:
            return (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(PurchaseBatch.id == batch_id, PurchaseBatch.is_deleted == False)
                .first()
            )
        finally:
            session.close()

    @staticmethod
    def finish_batch(
        batch_id: int,
        business_date: date,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> PurchaseBatch:
        """
        Explicitly marks a batch as completely finished (CLOSED).
        If stock > 0, requires a reason to record stock adjustment bringing it to 0.
        Negative stock cannot be closed.
        """
        with session_scope() as session:
            batch = (
                session.query(PurchaseBatch)
                .filter(PurchaseBatch.id == batch_id, PurchaseBatch.is_deleted == False)
                .with_for_update()
                .first()
            )
            if not batch:
                raise ValueError(f"Batch #{batch_id} not found.")

            if batch.status == "CLOSED":
                raise ValueError(f"Batch {batch.batch_number} is already closed.")

            if batch.current_stock_kg < 0:
                raise ValueError(f"Cannot close batch {batch.batch_number} with negative stock balance ({batch.current_stock_kg} KG).")

            # If there is remaining stock, require resolution via stock adjustment
            if batch.current_stock_kg > 0:
                if not reason or not reason.strip():
                    raise ValueError(
                        f"Batch {batch.batch_number} has {batch.current_stock_kg} KG remaining stock. "
                        f"An explicit reason is required to record the final zeroing stock adjustment."
                    )
                diff = -batch.current_stock_kg
                InventoryService.record_movement(
                    session=session,
                    batch_id=batch.id,
                    movement_type="STOCK_ADJUSTMENT",
                    quantity_kg=diff,
                    business_date=business_date,
                    reference_type="BATCH_CLOSURE",
                    reference_id=batch.id,
                    reason=reason.strip(),
                    notes=notes.strip() if notes else "Final zeroing on batch completion"
                )

            batch.status = "CLOSED"
            batch.closed_at = datetime.now(timezone.utc)
            batch.closed_notes = notes.strip() if notes else (reason.strip() if reason else "Completed")
            session.flush()
            return batch

    @staticmethod
    def reopen_batch(batch_id: int, reason: str, notes: Optional[str] = None) -> PurchaseBatch:
        """Explicitly reopens a CLOSED batch with audit logging."""
        if not reason or not reason.strip():
            raise ValueError("A reason is required to reopen a closed batch.")

        with session_scope() as session:
            batch = (
                session.query(PurchaseBatch)
                .filter(PurchaseBatch.id == batch_id, PurchaseBatch.is_deleted == False)
                .with_for_update()
                .first()
            )
            if not batch:
                raise ValueError(f"Batch #{batch_id} not found.")

            if batch.status != "CLOSED":
                raise ValueError(f"Batch {batch.batch_number} is not closed (current status: {batch.status}).")

            batch.status = "ACTIVE" if batch.current_stock_kg > 0 else "DEPLETED"
            audit_entry = f"Reopened on {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}: {reason.strip()}"
            if notes and notes.strip():
                audit_entry += f" [{notes.strip()}]"
            batch.closed_notes = f"{batch.closed_notes or ''}\n{audit_entry}".strip()
            batch.closed_at = None
            session.flush()
            return batch

    @staticmethod
    def get_batch_history(batch_id: int) -> Dict[str, Any]:
        """Returns the complete transaction history and audit trail for a batch."""
        session = get_session()
        try:
            batch = (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(PurchaseBatch.id == batch_id)
                .first()
            )
            if not batch:
                return {}

            movements = (
                session.query(InventoryMovement)
                .filter(InventoryMovement.batch_id == batch_id)
                .order_by(InventoryMovement.business_date.asc(), InventoryMovement.id.asc())
                .all()
            )

            allocations = (
                session.query(SaleBatchAllocation)
                .options(joinedload(SaleBatchAllocation.sale))
                .filter(SaleBatchAllocation.batch_id == batch_id)
                .order_by(SaleBatchAllocation.id.asc())
                .all()
            )

            reconciliations = (
                session.query(DailyStockReconciliation)
                .filter(DailyStockReconciliation.batch_id == batch_id)
                .order_by(DailyStockReconciliation.business_date.asc(), DailyStockReconciliation.id.asc())
                .all()
            )

            returns = (
                session.query(CustomerReturnLine)
                .options(joinedload(CustomerReturnLine.customer_return))
                .filter(CustomerReturnLine.batch_id == batch_id)
                .order_by(CustomerReturnLine.id.asc())
                .all()
            )

            total_purchased = batch.net_weight_kg
            total_sold = sum((a.net_weight_kg for a in allocations), Decimal("0.000"))
            total_returned = sum((r.returned_net_weight_kg for r in returns if r.resale_eligible), Decimal("0.000"))
            total_loss = sum(
                (abs(m.quantity_kg) for m in movements if m.movement_type == "STOCK_LOSS"),
                Decimal("0.000")
            )
            total_gain = sum(
                (m.quantity_kg for m in movements if m.movement_type == "STOCK_GAIN"),
                Decimal("0.000")
            )

            return {
                "batch": batch,
                "movements": movements,
                "allocations": allocations,
                "reconciliations": reconciliations,
                "returns": returns,
                "total_purchased": round_weight(total_purchased),
                "total_sold": round_weight(total_sold),
                "total_returned": round_weight(total_returned),
                "total_loss": round_weight(total_loss),
                "total_gain": round_weight(total_gain),
                "current_stock": round_weight(batch.current_stock_kg),
                "status": batch.status
            }
        finally:
            session.close()
