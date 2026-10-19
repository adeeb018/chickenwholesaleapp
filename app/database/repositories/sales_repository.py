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
        if disc > gross_total:
            raise ValueError("Discount amount cannot exceed gross sale amount.")

        final_total = round_money(gross_total - disc)

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
        notes: Optional[str] = None
    ) -> Optional[Sale]:
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

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

