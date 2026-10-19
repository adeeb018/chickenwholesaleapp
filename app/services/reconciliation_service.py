from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session, session_scope
from app.database.models import (
    PurchaseBatch, DailyStockReconciliation, InventoryMovement, Item
)
from app.utils.decimal_utils import round_weight, to_decimal

class ReconciliationService:
    @staticmethod
    def get_batch_reconciliation_values(session: Session, batch: PurchaseBatch, business_date: date) -> Dict[str, Any]:
        """
        Calculates opening stock, daily additions, sales, returns, adjustments,
        and calculated closing stock for a batch on a given business date.
        """
        # 1. Determine Opening Stock for business_date
        # Find latest active reconciliation prior to business_date
        prior_recon = (
            session.query(DailyStockReconciliation)
            .filter(
                DailyStockReconciliation.batch_id == batch.id,
                DailyStockReconciliation.business_date < business_date,
                DailyStockReconciliation.is_active == True
            )
            .order_by(DailyStockReconciliation.business_date.desc(), DailyStockReconciliation.id.desc())
            .first()
        )

        if prior_recon:
            opening_stock = prior_recon.actual_closing_kg
            prior_date = prior_recon.business_date
            # Add movements between prior_date and business_date (excluding any prior reconciliation adjustments)
            interim_movements = (
                session.query(InventoryMovement)
                .filter(
                    InventoryMovement.batch_id == batch.id,
                    InventoryMovement.business_date > prior_date,
                    InventoryMovement.business_date < business_date
                )
                .all()
            )
            opening_stock += sum((m.quantity_kg for m in interim_movements), Decimal("0.000"))
        else:
            # No prior reconciliation: opening stock is sum of all movements before business_date
            prior_movements = (
                session.query(InventoryMovement)
                .filter(
                    InventoryMovement.batch_id == batch.id,
                    InventoryMovement.business_date < business_date
                )
                .all()
            )
            opening_stock = sum((m.quantity_kg for m in prior_movements), Decimal("0.000"))

        opening_stock = round_weight(opening_stock)

        # 2. Movements on business_date (excluding any reconciliation adjustment for business_date itself)
        day_movements = (
            session.query(InventoryMovement)
            .filter(
                InventoryMovement.batch_id == batch.id,
                InventoryMovement.business_date == business_date
            )
            .all()
        )

        stock_additions = Decimal("0.000")
        sales = Decimal("0.000")
        returns = Decimal("0.000")
        other_adjustments = Decimal("0.000")

        for m in day_movements:
            # Skip movements originating from reconciliation on this date
            if m.reference_type == "RECONCILIATION":
                continue

            if m.movement_type == "PURCHASE":
                stock_additions += m.quantity_kg
            elif m.movement_type == "SALE":
                sales += abs(m.quantity_kg)
            elif m.movement_type == "CUSTOMER_RETURN":
                returns += m.quantity_kg
            elif m.movement_type == "STOCK_GAIN":
                stock_additions += m.quantity_kg
            elif m.movement_type in ("STOCK_LOSS", "STOCK_ADJUSTMENT"):
                other_adjustments += m.quantity_kg

        stock_additions = round_weight(stock_additions)
        sales = round_weight(sales)
        returns = round_weight(returns)
        other_adjustments = round_weight(other_adjustments)

        # Calculated closing stock = Opening + Additions - Sales + Returns + Other Adjustments
        calculated_closing = round_weight(opening_stock + stock_additions - sales + returns + other_adjustments)

        # Check if batch is already reconciled for this date
        active_recon = (
            session.query(DailyStockReconciliation)
            .filter(
                DailyStockReconciliation.batch_id == batch.id,
                DailyStockReconciliation.business_date == business_date,
                DailyStockReconciliation.is_active == True
            )
            .first()
        )

        return {
            "batch": batch,
            "opening_stock": opening_stock,
            "stock_additions": stock_additions,
            "sales": sales,
            "returns": returns,
            "other_adjustments": other_adjustments,
            "calculated_closing": calculated_closing,
            "active_recon": active_recon,
            "is_reconciled": active_recon is not None,
            "actual_closing": active_recon.actual_closing_kg if active_recon else None,
            "difference": active_recon.difference_kg if active_recon else None,
            "reason": active_recon.reason if active_recon else None,
            "notes": active_recon.notes if active_recon else None
        }

    @staticmethod
    def get_batch_reconciliation(batch_id: int, business_date: date) -> Optional[Dict[str, Any]]:
        """Convenience method to retrieve reconciliation values for a single batch on business_date."""
        session = get_session()
        try:
            batch = (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(PurchaseBatch.id == batch_id)
                .first()
            )
            if not batch:
                return None
            return ReconciliationService.get_batch_reconciliation_values(session, batch, business_date)
        finally:
            session.close()

    @staticmethod
    def get_reconciliation_sheet(business_date: date) -> List[Dict[str, Any]]:
        """
        Retrieves all batches eligible for daily physical reconciliation on business_date.
        Includes newly purchased batches, active batches, and carried-forward stock.
        """
        session = get_session()
        try:
            # Find all batches with purchase_date <= business_date
            batches = (
                session.query(PurchaseBatch)
                .options(joinedload(PurchaseBatch.item), joinedload(PurchaseBatch.purchase))
                .filter(
                    PurchaseBatch.is_deleted == False,
                    PurchaseBatch.purchase_date <= business_date
                )
                .order_by(PurchaseBatch.purchase_date.asc(), PurchaseBatch.id.asc())
                .all()
            )

            results = []
            for b in batches:
                # If closed before business_date with 0 stock and no movements on business_date, skip
                values = ReconciliationService.get_batch_reconciliation_values(session, b, business_date)
                
                # Check if it should be displayed:
                # If it had opening stock > 0, or additions > 0, or sales > 0, or returns > 0, or is reconciled, or current status != CLOSED
                had_activity = (
                    values["opening_stock"] > 0 or
                    values["stock_additions"] > 0 or
                    values["sales"] > 0 or
                    values["returns"] > 0 or
                    values["calculated_closing"] > 0 or
                    values["is_reconciled"] or
                    b.status != "CLOSED"
                )
                if had_activity:
                    results.append(values)

            return results
        finally:
            session.close()

    @staticmethod
    def reconcile_batch(
        batch_id: int,
        business_date: date,
        actual_closing_stock: any,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> DailyStockReconciliation:
        """
        Records daily physical reconciliation for a batch.
        Updates inventory ledger with STOCK_LOSS or STOCK_GAIN if discrepancy exists.
        Daily reconciliation does NOT close the batch.
        """
        actual_stock = round_weight(actual_closing_stock)
        if actual_stock < 0:
            raise ValueError("Actual closing stock cannot be negative.")

        with session_scope() as session:
            batch = (
                session.query(PurchaseBatch)
                .filter(PurchaseBatch.id == batch_id, PurchaseBatch.is_deleted == False)
                .with_for_update()
                .first()
            )
            if not batch:
                raise ValueError(f"Batch #{batch_id} not found.")

            # Check for existing active reconciliation for this date
            existing = (
                session.query(DailyStockReconciliation)
                .filter(
                    DailyStockReconciliation.batch_id == batch.id,
                    DailyStockReconciliation.business_date == business_date,
                    DailyStockReconciliation.is_active == True
                )
                .first()
            )
            if existing:
                raise ValueError(
                    f"Batch {batch.batch_number} is already reconciled for {business_date.strftime('%d/%m/%Y')}. "
                    f"Use correct_reconciliation to amend an existing record."
                )

            values = ReconciliationService.get_batch_reconciliation_values(session, batch, business_date)
            calculated_stock = values["calculated_closing"]
            difference = round_weight(actual_stock - calculated_stock)

            recon = DailyStockReconciliation(
                batch_id=batch.id,
                business_date=business_date,
                opening_stock_kg=values["opening_stock"],
                stock_additions_kg=values["stock_additions"],
                sales_kg=values["sales"],
                returns_kg=values["returns"],
                other_adjustments_kg=values["other_adjustments"],
                calculated_closing_kg=calculated_stock,
                actual_closing_kg=actual_stock,
                difference_kg=difference,
                status="RECONCILED",
                reason=reason.strip() if reason else None,
                notes=notes.strip() if notes else None,
                is_active=True,
                version=1
            )
            session.add(recon)
            session.flush()

            # Record inventory movement if discrepancy != 0
            if difference < 0:
                # Stock loss
                movement = InventoryMovement(
                    batch_id=batch.id,
                    movement_type="STOCK_LOSS",
                    quantity_kg=difference,  # negative
                    business_date=business_date,
                    reference_type="RECONCILIATION",
                    reference_id=recon.id,
                    reason=reason.strip() if reason else "Natural Weight Loss / Daily Reconciliation",
                    notes=notes
                )
                session.add(movement)
                batch.current_stock_kg = round_weight(batch.current_stock_kg + difference)
            elif difference > 0:
                # Stock gain
                movement = InventoryMovement(
                    batch_id=batch.id,
                    movement_type="STOCK_GAIN",
                    quantity_kg=difference,  # positive
                    business_date=business_date,
                    reference_type="RECONCILIATION",
                    reference_id=recon.id,
                    reason=reason.strip() if reason else "Weight Gain / Daily Reconciliation",
                    notes=notes
                )
                session.add(movement)
                batch.current_stock_kg = round_weight(batch.current_stock_kg + difference)

            # Update batch status (depleted vs active, but NOT closed)
            if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
                batch.status = "DEPLETED"
            elif batch.current_stock_kg > 0 and batch.status == "DEPLETED":
                batch.status = "ACTIVE"

            session.flush()
            return recon

    @staticmethod
    def correct_reconciliation(
        reconciliation_id: int,
        new_actual_closing_stock: any,
        reason: str,
        notes: Optional[str] = None
    ) -> DailyStockReconciliation:
        """
        Safely corrects an existing daily stock reconciliation.
        Marks old reconciliation as corrected and records a new version with adjustments.
        Preserves auditable history.
        """
        new_actual = round_weight(new_actual_closing_stock)
        if new_actual < 0:
            raise ValueError("Actual closing stock cannot be negative.")
        if not reason or not reason.strip():
            raise ValueError("Reason is required when correcting a reconciliation.")

        with session_scope() as session:
            old_recon = (
                session.query(DailyStockReconciliation)
                .filter(DailyStockReconciliation.id == reconciliation_id)
                .with_for_update()
                .first()
            )
            if not old_recon or not old_recon.is_active:
                raise ValueError("Reconciliation record not found or already corrected.")

            batch = (
                session.query(PurchaseBatch)
                .filter(PurchaseBatch.id == old_recon.batch_id)
                .with_for_update()
                .first()
            )

            # Revert old discrepancy movement from current stock
            if old_recon.difference_kg != 0:
                batch.current_stock_kg = round_weight(batch.current_stock_kg - old_recon.difference_kg)

            # Mark old reconciliation as inactive and corrected
            old_recon.is_active = False
            old_recon.status = "CORRECTED"

            # Remove or reverse old reconciliation movement
            old_movement = (
                session.query(InventoryMovement)
                .filter(
                    InventoryMovement.reference_type == "RECONCILIATION",
                    InventoryMovement.reference_id == old_recon.id
                )
                .first()
            )
            if old_movement:
                session.delete(old_movement)
                session.flush()

            # Recalculate difference with new actual stock
            new_diff = round_weight(new_actual - old_recon.calculated_closing_kg)

            new_recon = DailyStockReconciliation(
                batch_id=batch.id,
                business_date=old_recon.business_date,
                opening_stock_kg=old_recon.opening_stock_kg,
                stock_additions_kg=old_recon.stock_additions_kg,
                sales_kg=old_recon.sales_kg,
                returns_kg=old_recon.returns_kg,
                other_adjustments_kg=old_recon.other_adjustments_kg,
                calculated_closing_kg=old_recon.calculated_closing_kg,
                actual_closing_kg=new_actual,
                difference_kg=new_diff,
                status="RECONCILED",
                reason=reason.strip(),
                notes=notes.strip() if notes else f"Correction of reconciliation #{old_recon.id}",
                is_active=True,
                version=old_recon.version + 1
            )
            session.add(new_recon)
            session.flush()

            # Add new movement if difference != 0
            if new_diff < 0:
                m = InventoryMovement(
                    batch_id=batch.id,
                    movement_type="STOCK_LOSS",
                    quantity_kg=new_diff,
                    business_date=old_recon.business_date,
                    reference_type="RECONCILIATION",
                    reference_id=new_recon.id,
                    reason=f"Corrected Stock Loss: {reason.strip()}",
                    notes=notes
                )
                session.add(m)
                batch.current_stock_kg = round_weight(batch.current_stock_kg + new_diff)
            elif new_diff > 0:
                m = InventoryMovement(
                    batch_id=batch.id,
                    movement_type="STOCK_GAIN",
                    quantity_kg=new_diff,
                    business_date=old_recon.business_date,
                    reference_type="RECONCILIATION",
                    reference_id=new_recon.id,
                    reason=f"Corrected Stock Gain: {reason.strip()}",
                    notes=notes
                )
                session.add(m)
                batch.current_stock_kg = round_weight(batch.current_stock_kg + new_diff)

            if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
                batch.status = "DEPLETED"
            elif batch.current_stock_kg > 0 and batch.status == "DEPLETED":
                batch.status = "ACTIVE"

            session.flush()
            return new_recon

    @staticmethod
    def get_daily_closing_summary(business_date: date) -> Dict[str, Any]:
        """
        Returns the daily closing summary metrics for business_date.
        """
        sheet = ReconciliationService.get_reconciliation_sheet(business_date)
        total_batches = len(sheet)
        reconciled_batches = sum(1 for row in sheet if row["is_reconciled"])
        pending_batches = total_batches - reconciled_batches

        total_expected = sum((row["calculated_closing"] for row in sheet), Decimal("0.000"))
        total_actual = sum(
            (row["actual_closing"] for row in sheet if row["actual_closing"] is not None),
            Decimal("0.000")
        )

        total_loss = sum(
            (abs(row["difference"]) for row in sheet if row["difference"] is not None and row["difference"] < 0),
            Decimal("0.000")
        )
        total_gain = sum(
            (row["difference"] for row in sheet if row["difference"] is not None and row["difference"] > 0),
            Decimal("0.000")
        )
        discrepancy_batches = sum(
            1 for row in sheet if row["difference"] is not None and row["difference"] != 0
        )

        return {
            "business_date": business_date,
            "total_batches": total_batches,
            "reconciled_batches": reconciled_batches,
            "pending_batches": pending_batches,
            "total_expected_kg": round_weight(total_expected),
            "total_actual_kg": round_weight(total_actual),
            "total_loss_kg": round_weight(total_loss),
            "total_gain_kg": round_weight(total_gain),
            "discrepancy_batches": discrepancy_batches
        }
