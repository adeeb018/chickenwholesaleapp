from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from app.database.models import Purchase
from app.utils.decimal_utils import to_decimal, round_weight, round_money

class PurchaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, purchase_id: int) -> Optional[Purchase]:
        return (
            self.session.query(Purchase)
            .options(joinedload(Purchase.provider), joinedload(Purchase.item))
            .filter(Purchase.id == purchase_id, Purchase.is_deleted == False)
            .first()
        )

    def get_purchases(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_id: Optional[int] = None,
        item_id: Optional[int] = None,
        payment_type: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[Purchase]:
        query = (
            self.session.query(Purchase)
            .options(joinedload(Purchase.provider), joinedload(Purchase.item))
            .filter(Purchase.is_deleted == False)
        )

        if start_date:
            query = query.filter(Purchase.transaction_date >= start_date)
        if end_date:
            query = query.filter(Purchase.transaction_date <= end_date)
        if provider_id:
            query = query.filter(Purchase.provider_id == provider_id)
        if item_id:
            query = query.filter(Purchase.item_id == item_id)
        if payment_type:
            query = query.filter(Purchase.payment_type == payment_type.upper())
        if voucher_number:
            query = query.filter(Purchase.voucher_number.ilike(f"%{voucher_number.strip()}%"))

        return query.order_by(Purchase.transaction_date.desc(), Purchase.id.desc()).all()

    def create(
        self,
        transaction_date: date,
        provider_id: int,
        item_id: int,
        weight_kg: any = None,
        rate_per_kg: any = None,
        payment_type: str = "CASH",
        gross_weight_kg: any = None,
        box_weight_kg: any = 0.000,
        box_count: int = 0,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Purchase:
        if gross_weight_kg is not None:
            gross = round_weight(gross_weight_kg)
            box = round_weight(box_weight_kg) if box_weight_kg is not None else Decimal("0.000")
            if gross <= 0:
                raise ValueError("Gross weight must be greater than 0.")
            if box < 0:
                raise ValueError("Box weight cannot be negative.")
            if box > gross:
                raise ValueError("Box weight cannot be greater than gross weight.")
            net = round_weight(gross - box)
        elif weight_kg is not None:
            net = round_weight(weight_kg)
            if net <= 0:
                raise ValueError("Gross weight must be greater than 0.")
            gross = net
            box = Decimal("0.000")
        else:
            raise ValueError("Gross weight must be greater than 0.")

        box_cnt = int(box_count or 0)
        if box_cnt < 0:
            raise ValueError("Box count cannot be negative.")

        rate = round_money(rate_per_kg)
        total = round_money(net * rate)

        purchase = Purchase(
            transaction_date=transaction_date,
            provider_id=provider_id,
            item_id=item_id,
            box_count=box_cnt,
            gross_weight_kg=gross,
            box_weight_kg=box,
            net_weight_kg=net,
            weight_kg=net,
            rate_per_kg=rate,
            total_amount=total,
            payment_type=payment_type.upper(),
            voucher_number=voucher_number.strip() if voucher_number else None,
            bank_reference=bank_reference.strip() if bank_reference else None,
            notes=notes.strip() if notes else None
        )
        self.session.add(purchase)
        self.session.commit()
        self.session.refresh(purchase)
        return purchase

    def update(
        self,
        purchase_id: int,
        transaction_date: date,
        provider_id: int,
        item_id: int,
        weight_kg: any = None,
        rate_per_kg: any = None,
        payment_type: str = "CASH",
        gross_weight_kg: any = None,
        box_weight_kg: any = 0.000,
        box_count: int = 0,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Purchase]:
        purchase = self.get_by_id(purchase_id)
        if not purchase:
            return None

        if gross_weight_kg is not None:
            gross = round_weight(gross_weight_kg)
            box = round_weight(box_weight_kg) if box_weight_kg is not None else Decimal("0.000")
            if gross <= 0:
                raise ValueError("Gross weight must be greater than 0.")
            if box < 0:
                raise ValueError("Box weight cannot be negative.")
            if box > gross:
                raise ValueError("Box weight cannot be greater than gross weight.")
            net = round_weight(gross - box)
        elif weight_kg is not None:
            net = round_weight(weight_kg)
            if net <= 0:
                raise ValueError("Gross weight must be greater than 0.")
            gross = net
            box = Decimal("0.000")
        else:
            raise ValueError("Gross weight must be greater than 0.")

        box_cnt = int(box_count or 0)
        if box_cnt < 0:
            raise ValueError("Box count cannot be negative.")

        rate = round_money(rate_per_kg)
        total = round_money(net * rate)

        purchase.transaction_date = transaction_date
        purchase.provider_id = provider_id
        purchase.item_id = item_id
        purchase.box_count = box_cnt
        purchase.gross_weight_kg = gross
        purchase.box_weight_kg = box
        purchase.net_weight_kg = net
        purchase.weight_kg = net
        purchase.rate_per_kg = rate
        purchase.total_amount = total
        purchase.payment_type = payment_type.upper()
        purchase.voucher_number = voucher_number.strip() if voucher_number else None
        purchase.bank_reference = bank_reference.strip() if bank_reference else None
        purchase.notes = notes.strip() if notes else None

        self.session.commit()
        self.session.refresh(purchase)
        return purchase

    def soft_delete(self, purchase_id: int) -> bool:
        purchase = self.get_by_id(purchase_id)
        if not purchase:
            return False
        purchase.soft_delete()
        self.session.commit()
        return True
