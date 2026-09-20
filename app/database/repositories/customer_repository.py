from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.database.models import Customer, CustomerOpeningBalance
from app.utils.decimal_utils import to_decimal

class CustomerRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, include_inactive: bool = False) -> List[Customer]:
        query = (
            self.session.query(Customer)
            .options(joinedload(Customer.opening_balance))
            .filter(Customer.is_deleted == False)
        )
        if not include_inactive:
            query = query.filter(Customer.is_active == True)
        return query.order_by(Customer.name.asc()).all()

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        return (
            self.session.query(Customer)
            .options(joinedload(Customer.opening_balance))
            .filter(Customer.id == customer_id, Customer.is_deleted == False)
            .first()
        )

    def search(self, query_str: str) -> List[Customer]:
        pattern = f"%{query_str}%"
        return (
            self.session.query(Customer)
            .options(joinedload(Customer.opening_balance))
            .filter(
                Customer.is_deleted == False,
                (Customer.name.ilike(pattern) | Customer.phone.ilike(pattern))
            )
            .order_by(Customer.name.asc())
            .all()
        )

    def create(
        self,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Customer:
        customer = Customer(
            name=name.strip(),
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            notes=notes.strip() if notes else None,
            is_active=True
        )
        self.session.add(customer)
        self.session.flush()

        if opening_balance is not None or opening_balance_date is not None:
            op_date = opening_balance_date or date.today()
            op_amt = to_decimal(opening_balance or 0)
            op = CustomerOpeningBalance(
                customer_id=customer.id,
                amount=op_amt,
                as_of_date=op_date,
                notes="Initial Opening Balance"
            )
            self.session.add(op)

        self.session.commit()
        self.session.refresh(customer)
        return customer

    def update(
        self,
        customer_id: int,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_active: bool = True,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Optional[Customer]:
        customer = self.get_by_id(customer_id)
        if not customer:
            return None

        customer.name = name.strip()
        customer.phone = phone.strip() if phone else None
        customer.address = address.strip() if address else None
        customer.notes = notes.strip() if notes else None
        customer.is_active = is_active

        if opening_balance is not None or opening_balance_date is not None:
            op_amt = to_decimal(opening_balance or 0)
            op_date = opening_balance_date or date.today()

            if customer.opening_balance:
                customer.opening_balance.amount = op_amt
                customer.opening_balance.as_of_date = op_date
            else:
                op = CustomerOpeningBalance(
                    customer_id=customer.id,
                    amount=op_amt,
                    as_of_date=op_date,
                    notes="Initial Opening Balance"
                )
                self.session.add(op)

        self.session.commit()
        self.session.refresh(customer)
        return customer

    def soft_delete(self, customer_id: int) -> bool:
        customer = self.get_by_id(customer_id)
        if not customer:
            return False
        customer.soft_delete()
        self.session.commit()
        return True
