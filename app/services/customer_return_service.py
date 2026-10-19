from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session, session_scope
from app.database.models import (
    CustomerReturn, CustomerReturnLine, Sale, SaleBatchAllocation,
    PurchaseBatch, InventoryMovement, Customer
)
from app.utils.decimal_utils import round_weight, round_money, to_decimal

class CustomerReturnService:
    @staticmethod
    def get_next_return_number(session: Session, return_date: date) -> str:
        """Generates sequential unique return numbers like 'CR-20261019-001'."""
        date_str = return_date.strftime("%Y%m%d")
        prefix = f"CR-{date_str}-"
        count = (
            session.query(CustomerReturn)
            .filter(CustomerReturn.return_number.like(f"{prefix}%"))
            .count()
        )
        return f"{prefix}{count + 1:03d}"

    @staticmethod
    def create_customer_return(
        customer_id: int,
        original_sale_id: int,
        return_date: date,
        lines_data: List[Dict[str, Any]],
        notes: Optional[str] = None,
        reopen_if_closed: bool = False
    ) -> CustomerReturn:
        """
        Creates a customer return against an original sale.
        Validates returnable quantities per allocation or sale.
        Customer can return only if the batch is not closed; if closed,
        reopening is required before return can be accepted.
        Updates customer financial accounting atomically.
        """
        if not lines_data:
            raise ValueError("At least one return item line is required.")

        with session_scope() as session:
            sale = (
                session.query(Sale)
                .options(joinedload(Sale.allocations))
                .filter(Sale.id == original_sale_id, Sale.is_deleted == False)
                .first()
            )
            if not sale:
                raise ValueError(f"Sale #{original_sale_id} not found.")

            if sale.customer_id != customer_id:
                raise ValueError(f"Sale #{original_sale_id} does not belong to customer #{customer_id}.")

            ret_num = CustomerReturnService.get_next_return_number(session, return_date)

            total_returned_weight = Decimal("0.000")
            total_credit_amount = Decimal("0.00")

            customer_return = CustomerReturn(
                return_number=ret_num,
                customer_id=customer_id,
                original_sale_id=original_sale_id,
                return_date=return_date,
                total_returned_weight_kg=Decimal("0.000"),
                financial_credit_amount=Decimal("0.00"),
                notes=notes.strip() if notes else None
            )
            session.add(customer_return)
            session.flush()

            for line in lines_data:
                alloc_id = line.get("sale_batch_allocation_id")
                batch_id = line.get("batch_id")
                gross_w = round_weight(line.get("returned_gross_weight_kg", 0))
                box_w = round_weight(line.get("returned_box_weight_kg", 0))
                net_w = round_weight(line.get("returned_net_weight_kg") or (gross_w - box_w))
                resale = bool(line.get("resale_eligible", True))
                reason = line.get("reason", "").strip() or None
                line_notes = line.get("notes", "").strip() or None

                if net_w <= 0:
                    raise ValueError("Returned net weight must be greater than 0.")

                # Allocation validation
                alloc = None
                if alloc_id:
                    alloc = session.query(SaleBatchAllocation).filter(SaleBatchAllocation.id == alloc_id).first()
                    if not alloc or alloc.sale_id != sale.id:
                        raise ValueError(f"Sale allocation #{alloc_id} does not belong to sale #{sale.id}.")
                    batch_id = alloc.batch_id
                    rate = round_money(line.get("rate_per_kg") or alloc.rate_per_kg)

                    # Validate total returned against this allocation
                    prev_returned = (
                        session.query(CustomerReturnLine)
                        .filter(CustomerReturnLine.sale_batch_allocation_id == alloc.id, CustomerReturnLine.is_deleted == False)
                        .all()
                    )
                    prev_qty = sum((l.returned_net_weight_kg for l in prev_returned), Decimal("0.000"))
                    if prev_qty + net_w > alloc.net_weight_kg:
                        max_avail = alloc.net_weight_kg - prev_qty
                        raise ValueError(
                            f"Returned quantity ({net_w} KG) exceeds returnable limit for batch allocation #{alloc.id}. "
                            f"Original sold: {alloc.net_weight_kg} KG, already returned: {prev_qty} KG, max available: {max_avail} KG."
                        )
                else:
                    # Sale-level validation
                    rate = round_money(line.get("rate_per_kg") or sale.rate_per_kg)
                    if not batch_id:
                        # If sale has allocations, require choosing allocation or batch
                        if sale.allocations:
                            alloc = sale.allocations[0]
                            batch_id = alloc.batch_id
                            alloc_id = alloc.id
                        else:
                            # Try to find a matching batch for this item
                            latest_batch = (
                                session.query(PurchaseBatch)
                                .filter(PurchaseBatch.item_id == sale.item_id, PurchaseBatch.is_deleted == False)
                                .order_by(PurchaseBatch.id.desc())
                                .first()
                            )
                            if not latest_batch:
                                raise ValueError(f"No batch found to associate with returned item for sale #{sale.id}.")
                            batch_id = latest_batch.id

                    # Check overall sale return limits
                    prev_lines = (
                        session.query(CustomerReturnLine)
                        .join(CustomerReturn, CustomerReturnLine.customer_return_id == CustomerReturn.id)
                        .filter(CustomerReturn.original_sale_id == sale.id, CustomerReturnLine.is_deleted == False)
                        .all()
                    )
                    prev_qty = sum((l.returned_net_weight_kg for l in prev_lines), Decimal("0.000"))
                    if prev_qty + net_w > sale.net_weight_kg:
                        max_avail = sale.net_weight_kg - prev_qty
                        raise ValueError(
                            f"Returned quantity ({net_w} KG) exceeds returnable limit for sale #{sale.id}. "
                            f"Original sold: {sale.net_weight_kg} KG, already returned: {prev_qty} KG, max available: {max_avail} KG."
                        )

                line_amount = round_money(net_w * rate)
                total_returned_weight += net_w
                total_credit_amount += line_amount

                batch = (
                    session.query(PurchaseBatch)
                    .filter(PurchaseBatch.id == batch_id)
                    .with_for_update()
                    .first()
                )
                if not batch:
                    raise ValueError(f"Batch #{batch_id} not found.")

                if batch.status == "CLOSED":
                    if not reopen_if_closed:
                        raise ValueError(
                            f"Batch '{batch.batch_number}' is CLOSED. "
                            f"Customer returns cannot be processed for a closed batch unless it is reopened."
                        )
                    # Reopen closed batch
                    batch.status = "ACTIVE"
                    reopen_mov = InventoryMovement(
                        batch_id=batch.id,
                        movement_type="REOPEN_BATCH",
                        quantity_kg=Decimal("0.000"),
                        business_date=return_date,
                        reference_type="CUSTOMER_RETURN",
                        reason="Reopened to accept customer return",
                        notes=f"Reopened for Return #{customer_return.return_number}"
                    )
                    session.add(reopen_mov)
                    session.flush()

                box_cnt = int(line.get("box_count", 0) or 0)

                return_line = CustomerReturnLine(
                    customer_return_id=customer_return.id,
                    sale_batch_allocation_id=alloc_id,
                    batch_id=batch_id,
                    box_count=box_cnt,
                    returned_gross_weight_kg=gross_w if gross_w > 0 else net_w,
                    returned_box_weight_kg=box_w,
                    returned_net_weight_kg=net_w,
                    rate_per_kg=rate,
                    financial_amount=line_amount,
                    resale_eligible=resale,
                    reason=reason,
                    notes=line_notes
                )
                session.add(return_line)
                session.flush()

                # Inventory update:
                # If resale_eligible is True, restore sellable stock to the active/reopened batch
                if resale:
                    movement = InventoryMovement(
                        batch_id=batch.id,
                        movement_type="CUSTOMER_RETURN",
                        quantity_kg=net_w,
                        business_date=return_date,
                        reference_type="CUSTOMER_RETURN",
                        reference_id=customer_return.id,
                        reason=reason or "Customer Return (Resale Eligible)",
                        notes=line_notes
                    )
                    session.add(movement)
                    batch.current_stock_kg = round_weight(batch.current_stock_kg + net_w)
                    if batch.status == "DEPLETED" and batch.current_stock_kg > 0:
                        batch.status = "ACTIVE"
                    session.flush()

            customer_return.total_returned_weight_kg = round_weight(total_returned_weight)
            customer_return.financial_credit_amount = round_money(total_credit_amount)
            session.flush()
            return customer_return

    @staticmethod
    def get_returns(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        batch_id: Optional[int] = None
    ) -> List[CustomerReturn]:
        """Queries customer returns with filters."""
        session = get_session()
        try:
            query = (
                session.query(CustomerReturn)
                .options(
                    joinedload(CustomerReturn.customer),
                    joinedload(CustomerReturn.original_sale),
                    joinedload(CustomerReturn.lines).joinedload(CustomerReturnLine.batch)
                )
                .filter(CustomerReturn.is_deleted == False)
            )
            if start_date:
                query = query.filter(CustomerReturn.return_date >= start_date)
            if end_date:
                query = query.filter(CustomerReturn.return_date <= end_date)
            if customer_id:
                query = query.filter(CustomerReturn.customer_id == customer_id)
            if batch_id:
                query = query.join(CustomerReturn.lines).filter(CustomerReturnLine.batch_id == batch_id)

            return query.order_by(CustomerReturn.return_date.desc(), CustomerReturn.id.desc()).all()
        finally:
            session.close()

    @staticmethod
    def get_return_by_id(return_id: int) -> Optional[CustomerReturn]:
        session = get_session()
        try:
            return (
                session.query(CustomerReturn)
                .options(
                    joinedload(CustomerReturn.customer),
                    joinedload(CustomerReturn.original_sale),
                    joinedload(CustomerReturn.lines).joinedload(CustomerReturnLine.batch)
                )
                .filter(CustomerReturn.id == return_id, CustomerReturn.is_deleted == False)
                .first()
            )
        finally:
            session.close()

    @staticmethod
    def get_returnable_sale_info(sale_id: int) -> Dict[str, Any]:
        """
        Returns details of a sale and its allocations with remaining returnable quantities.
        """
        session = get_session()
        try:
            sale = (
                session.query(Sale)
                .options(joinedload(Sale.allocations).joinedload(SaleBatchAllocation.batch))
                .filter(Sale.id == sale_id, Sale.is_deleted == False)
                .first()
            )
            if not sale:
                return {}

            allocations_info = []
            if sale.allocations:
                for a in sale.allocations:
                    prev_lines = (
                        session.query(CustomerReturnLine)
                        .filter(CustomerReturnLine.sale_batch_allocation_id == a.id, CustomerReturnLine.is_deleted == False)
                        .all()
                    )
                    already_returned = sum((l.returned_net_weight_kg for l in prev_lines), Decimal("0.000"))
                    returnable = max(Decimal("0.000"), a.net_weight_kg - already_returned)
                    allocations_info.append({
                        "allocation_id": a.id,
                        "batch_id": a.batch_id,
                        "batch_number": a.batch.batch_number if a.batch else f"Batch #{a.batch_id}",
                        "sold_net_kg": a.net_weight_kg,
                        "already_returned_kg": round_weight(already_returned),
                        "returnable_kg": round_weight(returnable),
                        "rate_per_kg": a.rate_per_kg
                    })
            else:
                prev_lines = (
                    session.query(CustomerReturnLine)
                    .join(CustomerReturn, CustomerReturnLine.customer_return_id == CustomerReturn.id)
                    .filter(CustomerReturn.original_sale_id == sale.id, CustomerReturnLine.is_deleted == False)
                    .all()
                )
                already_returned = sum((l.returned_net_weight_kg for l in prev_lines), Decimal("0.000"))
                returnable = max(Decimal("0.000"), sale.net_weight_kg - already_returned)
                allocations_info.append({
                    "allocation_id": None,
                    "batch_id": None,
                    "batch_number": "Default",
                    "sold_net_kg": sale.net_weight_kg,
                    "already_returned_kg": round_weight(already_returned),
                    "returnable_kg": round_weight(returnable),
                    "rate_per_kg": sale.rate_per_kg
                })

            return {
                "sale": sale,
                "allocations": allocations_info
            }
        finally:
            session.close()

    @staticmethod
    def soft_delete_customer_return(return_id: int) -> bool:
        """
        Soft-deletes a customer return, reversing restored inventory stock
        and removing the financial credit atomically.
        """
        with session_scope() as session:
            cr = session.query(CustomerReturn).filter(CustomerReturn.id == return_id, CustomerReturn.is_deleted == False).first()
            if not cr:
                return False

            cr.is_deleted = True
            cr.deleted_at = datetime.now(timezone.utc)

            for line in cr.lines:
                line.is_deleted = True
                line.deleted_at = datetime.now(timezone.utc)
                if line.resale_eligible and line.batch_id:
                    batch = session.query(PurchaseBatch).filter(PurchaseBatch.id == line.batch_id).first()
                    if batch:
                        rev_mov = InventoryMovement(
                            batch_id=batch.id,
                            movement_type="STOCK_ADJUSTMENT",
                            quantity_kg=-line.returned_net_weight_kg,
                            business_date=date.today(),
                            reference_type="RETURN_DELETION",
                            reference_id=cr.id,
                            reason="Reversal of deleted customer return",
                            notes=f"Return #{cr.return_number} deleted"
                        )
                        session.add(rev_mov)
                        batch.current_stock_kg = round_weight(max(Decimal("0.000"), batch.current_stock_kg - line.returned_net_weight_kg))
                        if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
                            batch.status = "DEPLETED"

            return True
