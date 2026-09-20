from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.database.models import Sale
from app.utils.decimal_utils import round_weight, round_money, to_decimal

class SalesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, sale_id: int) -> Optional[Sale]:
        return (
            self.session.query(Sale)
            .options(joinedload(Sale.customer), joinedload(Sale.item))
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
            .options(joinedload(Sale.customer), joinedload(Sale.item))
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
        notes: Optional[str] = None
    ) -> Sale:
        gross = round_weight(gross_weight_kg)
        box = round_weight(box_weight_kg)
        
        if gross <= 0:
            raise ValueError("Gross weight must be greater than 0.")
        if box < 0:
            raise ValueError("Box weight cannot be negative.")
        if box > gross:
            raise ValueError("Box weight cannot be greater than gross weight.")

        net = round_weight(gross - box)
        rate = round_money(rate_per_kg)
        gross_total = round_money(net * rate)
        disc = round_money(discount_amount)

        if disc < 0:
            raise ValueError("Discount amount cannot be negative.")
        if disc > gross_total:
            raise ValueError("Discount amount cannot exceed gross sale amount.")

        final_total = round_money(gross_total - disc)

        sale = Sale(
            transaction_date=transaction_date,
            customer_id=customer_id,
            item_id=item_id,
            gross_weight_kg=gross,
            box_weight_kg=box,
            net_weight_kg=net,
            rate_per_kg=rate,
            discount_amount=disc,
            total_amount=final_total,
            notes=notes.strip() if notes else None
        )
        self.session.add(sale)
        self.session.commit()
        self.session.refresh(sale)
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
        notes: Optional[str] = None
    ) -> Optional[Sale]:
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

        gross = round_weight(gross_weight_kg)
        box = round_weight(box_weight_kg)
        
        if gross <= 0:
            raise ValueError("Gross weight must be greater than 0.")
        if box < 0:
            raise ValueError("Box weight cannot be negative.")
        if box > gross:
            raise ValueError("Box weight cannot be greater than gross weight.")

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
        sale.soft_delete()
        self.session.commit()
        return True
