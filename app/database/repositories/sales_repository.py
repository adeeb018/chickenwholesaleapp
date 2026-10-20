from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from app.database.models import Sale, PurchaseBatch, SaleBatchAllocation, InventoryMovement
from app.utils.decimal_utils import round_weight, round_money, to_decimal

class SalesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, sale_id: int) -> Optional[Sale]:
        return (
            self.session.query(Sale)
            .options(
                joinedload(Sale.customer),
                joinedload(Sale.item),
                joinedload(Sale.allocations).joinedload(SaleBatchAllocation.batch)
            )
            .filter(Sale.id == sale_id, Sale.is_deleted == False)
            .first()
        )

    def get_sales(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        item_id: Optional[int] = None
    ) -> List[Sale]:
        query = (
            self.session.query(Sale)
            .options(
                joinedload(Sale.customer),
                joinedload(Sale.item),
                joinedload(Sale.allocations).joinedload(SaleBatchAllocation.batch)
            )
            .filter(Sale.is_deleted == False)
        )

        if start_date:
            query = query.filter(Sale.transaction_date >= start_date)
        if end_date:
            query = query.filter(Sale.transaction_date <= end_date)
        if customer_id:
            query = query.filter(Sale.customer_id == customer_id)
        if item_id:
            query = query.filter(Sale.item_id == item_id)

        return query.order_by(Sale.transaction_date.desc(), Sale.id.desc()).all()

    def create(
        self,
        transaction_date: date,
        customer_id: int,
        item_id: int,
        gross_weight_kg: any,
        box_weight_kg: any,
        rate_per_kg: any,
        discount_amount: any = 0.00,
        box_count: int = 0,
        notes: Optional[str] = None,
        allocations: Optional[List[Dict[str, Any]]] = None,
        batch_id: Optional[int] = None
    ) -> Sale:
        gross = round_weight(gross_weight_kg)
        box = round_weight(box_weight_kg)
        box_cnt = int(box_count or 0)
        
        if gross <= 0:
            raise ValueError("Gross weight must be greater than 0.")
        if box < 0:
            raise ValueError("Box weight cannot be negative.")
        if box > gross:
            raise ValueError("Box weight cannot be greater than gross weight.")
        if box_cnt < 0:
            raise ValueError("Box count cannot be negative.")

        net = round_weight(gross - box)
        rate = round_money(rate_per_kg)
        gross_total = round_money(net * rate)
        disc = round_money(discount_amount)

        if disc < 0:
            raise ValueError("Discount amount cannot be negative.")

        # Resolve batch allocations
        if batch_id is not None and not allocations:
            allocations = [{
                "batch_id": batch_id,
                "gross_weight_kg": gross,
                "box_weight_kg": box,
                "box_count": box_cnt,
                "net_weight_kg": net,
                "rate_per_kg": rate
            }]

        from app.services.inventory_service import InventoryService

        if allocations:
            alloc_total_net = sum((round_weight(a.get("net_weight_kg", 0)) for a in allocations), Decimal("0.000"))
            if alloc_total_net != net:
                raise ValueError(
                    f"Sum of allocated batch weights ({alloc_total_net} KG) must equal sale net weight ({net} KG)."
                )

            # Recalculate gross total and effective rate from allocations
            gross_total = sum((round_money(round_weight(a["net_weight_kg"]) * round_money(a.get("rate_per_kg", rate))) for a in allocations), Decimal("0.00"))
            rate = round_money(gross_total / net) if net > 0 else rate
            if disc > gross_total:
                raise ValueError("Discount amount cannot exceed gross sale amount.")
            final_total = round_money(gross_total - disc)

            # Validate each batch
            for a in allocations:
                b_id = a.get("batch_id")
                b_net = round_weight(a.get("net_weight_kg", 0))
                if b_net <= 0:
                    raise ValueError("Allocated net weight must be greater than 0.")
                batch = (
                    self.session.query(PurchaseBatch)
                    .filter(PurchaseBatch.id == b_id, PurchaseBatch.is_deleted == False)
                    .with_for_update()
                    .first()
                )
                if not batch:
                    raise ValueError(f"Batch #{b_id} not found.")
                if batch.status == "CLOSED":
                    raise ValueError(f"Ordinary sales cannot be made from CLOSED batch '{batch.batch_number}'.")
                if b_net > batch.current_stock_kg:
                    raise ValueError(
                        f"Insufficient stock in batch '{batch.batch_number}': "
                        f"available {batch.current_stock_kg} KG, requested {b_net} KG."
                    )
        else:
            if disc > gross_total:
                raise ValueError("Discount amount cannot exceed gross sale amount.")
            final_total = round_money(gross_total - disc)
            # Check if active batches exist for this item
            active_batches = (
                self.session.query(PurchaseBatch)
                .filter(
                    PurchaseBatch.item_id == item_id,
                    PurchaseBatch.status == "ACTIVE",
                    PurchaseBatch.current_stock_kg > 0,
                    PurchaseBatch.is_deleted == False
                )
                .order_by(PurchaseBatch.purchase_date.asc(), PurchaseBatch.id.asc())
                .all()
            )
            if active_batches:
                remaining = net
                allocations = []
                for b in active_batches:
                    take = min(remaining, b.current_stock_kg)
                    allocations.append({
                        "batch_id": b.id,
                        "gross_weight_kg": take,
                        "box_weight_kg": Decimal("0.000"),
                        "box_count": 0,
                        "net_weight_kg": take,
                        "rate_per_kg": rate
                    })
                    remaining -= take
                    if remaining == 0:
                        break
                if remaining > 0:
                    raise ValueError(
                        f"Insufficient stock across available batches: required {net} KG, available {net - remaining} KG."
                    )
            else:
                allocations = []

        sale = Sale(
            transaction_date=transaction_date,
            customer_id=customer_id,
            item_id=item_id,
            box_count=box_cnt,
            gross_weight_kg=gross,
            box_weight_kg=box,
            net_weight_kg=net,
            rate_per_kg=rate,
            discount_amount=disc,
            total_amount=final_total,
            notes=notes.strip() if notes else None
        )
        self.session.add(sale)
        self.session.flush()

        # Create allocations and record inventory deductions
        if allocations:
            for a in allocations:
                b_id = a["batch_id"]
                b_net = round_weight(a["net_weight_kg"])
                b_gross = round_weight(a.get("gross_weight_kg", b_net))
                b_box = round_weight(a.get("box_weight_kg", 0))
                b_box_cnt = int(a.get("box_count", 0))
                b_rate = round_money(a.get("rate_per_kg", rate))
                b_amt = round_money(b_net * b_rate)

                alloc = SaleBatchAllocation(
                    sale_id=sale.id,
                    batch_id=b_id,
                    gross_weight_kg=b_gross,
                    box_weight_kg=b_box,
                    box_count=b_box_cnt,
                    net_weight_kg=b_net,
                    rate_per_kg=b_rate,
                    amount=b_amt
                )
                self.session.add(alloc)
                self.session.flush()

                InventoryService.record_movement(
                    session=self.session,
                    batch_id=b_id,
                    movement_type="SALE",
                    quantity_kg=-b_net,
                    business_date=transaction_date,
                    reference_type="SALE",
                    reference_id=sale.id,
                    reason=f"Customer Sale #{sale.id}"
                )

        self.session.commit()
        self.session.refresh(sale)
        _ = sale.allocations
        return sale

    def update(
        self,
        sale_id: int,
        transaction_date: date,
        customer_id: int,
        item_id: int,
        gross_weight_kg: any,
        box_weight_kg: any,
        rate_per_kg: any,
        discount_amount: any = 0.00,
        box_count: int = 0,
        notes: Optional[str] = None,
        allocations: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Sale]:
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

        from app.services.inventory_service import InventoryService
        from app.database.models import CustomerReturnLine

        # If allocations are provided, derive weights, rates, and amounts from them
        if allocations:
            tot_boxes = sum((int(a.get("box_count", 0)) for a in allocations), 0)
            tot_gross = sum((round_weight(a.get("gross_weight_kg", 0)) for a in allocations), Decimal("0.000"))
            tot_box = sum((round_weight(a.get("box_weight_kg", 0)) for a in allocations), Decimal("0.000"))
            tot_net = sum((round_weight(a.get("net_weight_kg", 0)) for a in allocations), Decimal("0.000"))

            for a in allocations:
                b_g = round_weight(a.get("gross_weight_kg", 0))
                b_b = round_weight(a.get("box_weight_kg", 0))
                b_n = round_weight(a.get("net_weight_kg", 0))
                if b_g <= 0:
                    raise ValueError("Allocated gross weight must be greater than 0.")
                if b_b > b_g:
                    raise ValueError("Box weight cannot exceed gross weight.")
                if b_n <= 0:
                    raise ValueError("Allocated net weight must be greater than 0.")

            gross = tot_gross
            box = tot_box
            box_cnt = tot_boxes
            net = tot_net
            gross_total = sum((round_money(round_weight(a["net_weight_kg"]) * round_money(a.get("rate_per_kg", rate_per_kg))) for a in allocations), Decimal("0.00"))
            rate = round_money(gross_total / net) if net > 0 else round_money(rate_per_kg)
        else:
            gross = round_weight(gross_weight_kg)
            box = round_weight(box_weight_kg)
            box_cnt = int(box_count or 0)
            if gross <= 0:
                raise ValueError("Gross weight must be greater than 0.")
            if box < 0:
                raise ValueError("Box weight cannot be negative.")
            if box > gross:
                raise ValueError("Box weight cannot be greater than gross weight.")
            if box_cnt < 0:
                raise ValueError("Box count cannot be negative.")
            net = round_weight(gross - box)
            rate = round_money(rate_per_kg)
            gross_total = round_money(net * rate)

        disc = round_money(discount_amount)
        if disc < 0:
            raise ValueError("Discount amount cannot be negative.")
        if disc > gross_total:
            raise ValueError("Discount amount cannot exceed gross sale amount.")
        final_total = round_money(gross_total - disc)

        # Validate returns if any exist
        if sale.returns:
            total_returned_weight = sum(
                (l.returned_net_weight_kg for ret in sale.returns if not ret.is_deleted for l in ret.lines if not l.is_deleted),
                Decimal("0.000")
            )
            if net < total_returned_weight:
                raise ValueError(
                    f"Sale net weight ({net} KG) cannot be reduced below already returned weight ({total_returned_weight} KG)."
                )

        # If allocations are provided, reconcile batch stock and allocations
        if allocations:
            # 1. Temporarily revert old allocations stock to batches
            old_allocs = list(sale.allocations) if sale.allocations else []
            old_alloc_map = {a.id: a for a in old_allocs}
            for old_a in old_allocs:
                b = self.session.query(PurchaseBatch).filter(PurchaseBatch.id == old_a.batch_id).with_for_update().first()
                if b:
                    b.current_stock_kg = round_weight(b.current_stock_kg + old_a.net_weight_kg)
                    if b.status == "DEPLETED" and b.current_stock_kg > 0:
                        b.status = "ACTIVE"

            # 2. Validate availability and deduct new allocations
            batch_usage = {}
            for a in allocations:
                b_id = a.get("batch_id")
                b_net = round_weight(a.get("net_weight_kg", 0))
                batch_usage[b_id] = batch_usage.get(b_id, Decimal("0.000")) + b_net

            for b_id, req_net in batch_usage.items():
                batch = self.session.query(PurchaseBatch).filter(PurchaseBatch.id == b_id).with_for_update().first()
                if not batch:
                    raise ValueError(f"Batch #{b_id} not found.")
                if batch.status == "CLOSED":
                    raise ValueError(f"Batch '{batch.batch_number}' is closed.")
                if req_net > batch.current_stock_kg:
                    raise ValueError(
                        f"Insufficient stock in batch '{batch.batch_number}': "
                        f"available {batch.current_stock_kg} KG, requested {req_net} KG."
                    )
                batch.current_stock_kg = round_weight(batch.current_stock_kg - req_net)
                if batch.current_stock_kg == 0 and batch.status == "ACTIVE":
                    batch.status = "DEPLETED"

            # 3. Synchronize SaleBatchAllocation records and movements
            # Remove old allocations that are no longer present
            kept_alloc_ids = {a.get("allocation_id") for a in allocations if a.get("allocation_id")}
            for old_a in old_allocs:
                if old_a.id not in kept_alloc_ids:
                    # Check returns
                    ret_cnt = self.session.query(CustomerReturnLine).filter(
                        CustomerReturnLine.sale_batch_allocation_id == old_a.id,
                        CustomerReturnLine.is_deleted == False
                    ).count()
                    if ret_cnt > 0:
                        raise ValueError(
                            f"Cannot remove allocation for batch #{old_a.batch_id} because customer returns exist for it."
                        )
                    self.session.query(InventoryMovement).filter(
                        InventoryMovement.batch_id == old_a.batch_id,
                        InventoryMovement.reference_type == "SALE",
                        InventoryMovement.reference_id == sale.id
                    ).delete()
                    self.session.delete(old_a)

            # Update existing or add new allocations
            for a in allocations:
                alloc_id = a.get("allocation_id")
                b_id = a.get("batch_id")
                b_cnt = int(a.get("box_count", 0))
                b_gross = round_weight(a.get("gross_weight_kg", 0))
                b_box = round_weight(a.get("box_weight_kg", 0))
                b_net = round_weight(a.get("net_weight_kg", 0))
                b_rate = round_money(a.get("rate_per_kg", rate))
                b_amt = round_money(b_net * b_rate)

                if alloc_id and alloc_id in old_alloc_map:
                    alloc_obj = old_alloc_map[alloc_id]
                    alloc_obj.batch_id = b_id
                    alloc_obj.box_count = b_cnt
                    alloc_obj.gross_weight_kg = b_gross
                    alloc_obj.box_weight_kg = b_box
                    alloc_obj.net_weight_kg = b_net
                    alloc_obj.rate_per_kg = b_rate
                    alloc_obj.amount = b_amt

                    mov = self.session.query(InventoryMovement).filter(
                        InventoryMovement.batch_id == b_id,
                        InventoryMovement.reference_type == "SALE",
                        InventoryMovement.reference_id == sale.id
                    ).first()
                    if mov:
                        mov.quantity_kg = -b_net
                        mov.business_date = transaction_date
                    else:
                        InventoryService.record_movement(
                            session=self.session,
                            batch_id=b_id,
                            movement_type="SALE",
                            quantity_kg=-b_net,
                            business_date=transaction_date,
                            reference_type="SALE",
                            reference_id=sale.id,
                            reason=f"Customer Sale #{sale.id}"
                        )
                else:
                    new_alloc = SaleBatchAllocation(
                        sale_id=sale.id,
                        batch_id=b_id,
                        gross_weight_kg=b_gross,
                        box_weight_kg=b_box,
                        box_count=b_cnt,
                        net_weight_kg=b_net,
                        rate_per_kg=b_rate,
                        amount=b_amt
                    )
                    self.session.add(new_alloc)
                    InventoryService.record_movement(
                        session=self.session,
                        batch_id=b_id,
                        movement_type="SALE",
                        quantity_kg=-b_net,
                        business_date=transaction_date,
                        reference_type="SALE",
                        reference_id=sale.id,
                        reason=f"Customer Sale #{sale.id}"
                    )

        sale.transaction_date = transaction_date
        sale.customer_id = customer_id
        sale.item_id = item_id
        sale.box_count = box_cnt
        sale.gross_weight_kg = gross
        sale.box_weight_kg = box
        sale.net_weight_kg = net
        sale.rate_per_kg = rate
        sale.discount_amount = disc
        sale.total_amount = final_total
        sale.notes = notes.strip() if notes else None

        self.session.commit()
        self.session.refresh(sale)
        _ = sale.allocations
        return sale

    def soft_delete(self, sale_id: int) -> bool:
        sale = self.get_by_id(sale_id)
        if not sale:
            return False

        if sale.returns:
            raise ValueError("Cannot delete sale: customer returns have already been processed for this sale.")

        # Revert batch inventory movements
        if sale.allocations:
            for alloc in sale.allocations:
                batch = (
                    self.session.query(PurchaseBatch)
                    .filter(PurchaseBatch.id == alloc.batch_id)
                    .with_for_update()
                    .first()
                )
                if batch:
                    batch.current_stock_kg = round_weight(batch.current_stock_kg + alloc.net_weight_kg)
                    if batch.status == "DEPLETED" and batch.current_stock_kg > 0:
                        batch.status = "ACTIVE"

                mov = (
                    self.session.query(InventoryMovement)
                    .filter(
                        InventoryMovement.batch_id == alloc.batch_id,
                        InventoryMovement.reference_type == "SALE",
                        InventoryMovement.reference_id == sale.id
                    )
                    .first()
                )
                if mov:
                    self.session.delete(mov)
                alloc.soft_delete()

        sale.soft_delete()
        self.session.commit()
        return True

