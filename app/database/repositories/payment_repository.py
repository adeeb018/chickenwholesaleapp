from typing import List, Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.database.models import CustomerPayment, ProviderPayment
from app.utils.decimal_utils import round_money, to_decimal

class PaymentRepository:
    def __init__(self, session: Session):
        self.session = session

    # --- Customer Payments ---
    def get_customer_payment_by_id(self, payment_id: int) -> Optional[CustomerPayment]:
        return (
            self.session.query(CustomerPayment)
            .options(joinedload(CustomerPayment.customer))
            .filter(CustomerPayment.id == payment_id, CustomerPayment.is_deleted == False)
            .first()
        )

    def get_customer_payments(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        payment_mode: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[CustomerPayment]:
        query = (
            self.session.query(CustomerPayment)
            .options(joinedload(CustomerPayment.customer))
            .filter(CustomerPayment.is_deleted == False)
        )

        if start_date:
            query = query.filter(CustomerPayment.payment_date >= start_date)
        if end_date:
            query = query.filter(CustomerPayment.payment_date <= end_date)
        if customer_id:
            query = query.filter(CustomerPayment.customer_id == customer_id)
        if payment_mode:
            query = query.filter(CustomerPayment.payment_mode == payment_mode.upper())
        if voucher_number:
            query = query.filter(CustomerPayment.voucher_number.ilike(f"%{voucher_number.strip()}%"))

        return query.order_by(CustomerPayment.payment_date.desc(), CustomerPayment.id.desc()).all()

    def create_customer_payment(
        self,
        payment_date: date,
        customer_id: int,
        amount: any,
        payment_mode: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CustomerPayment:
        amt = round_money(amount)
        if amt <= 0:
            raise ValueError("Payment amount must be greater than 0.")

        mode = payment_mode.upper()
        if mode not in ("CASH", "BANK"):
            raise ValueError("Payment mode must be CASH or BANK.")

        v_num = voucher_number.strip() if voucher_number else None
        if mode == "CASH" and not v_num:
            raise ValueError("Voucher number is required for CASH payments.")

        payment = CustomerPayment(
            payment_date=payment_date,
            customer_id=customer_id,
            amount=amt,
            payment_mode=mode,
            voucher_number=v_num,
            bank_reference=bank_reference.strip() if bank_reference else None,
            notes=notes.strip() if notes else None
        )
        self.session.add(payment)
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def soft_delete_customer_payment(self, payment_id: int) -> bool:
        p = self.get_customer_payment_by_id(payment_id)
        if not p:
            return False
        p.soft_delete()
        self.session.commit()
        return True

    # --- Provider Payments ---
    def get_provider_payment_by_id(self, payment_id: int) -> Optional[ProviderPayment]:
        return (
            self.session.query(ProviderPayment)
            .options(joinedload(ProviderPayment.provider))
            .filter(ProviderPayment.id == payment_id, ProviderPayment.is_deleted == False)
            .first()
        )

    def get_provider_payments(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_id: Optional[int] = None,
        payment_mode: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[ProviderPayment]:
        query = (
            self.session.query(ProviderPayment)
            .options(joinedload(ProviderPayment.provider))
            .filter(ProviderPayment.is_deleted == False)
        )

        if start_date:
            query = query.filter(ProviderPayment.payment_date >= start_date)
        if end_date:
            query = query.filter(ProviderPayment.payment_date <= end_date)
        if provider_id:
            query = query.filter(ProviderPayment.provider_id == provider_id)
        if payment_mode:
            query = query.filter(ProviderPayment.payment_mode == payment_mode.upper())
        if voucher_number:
            query = query.filter(ProviderPayment.voucher_number.ilike(f"%{voucher_number.strip()}%"))

        return query.order_by(ProviderPayment.payment_date.desc(), ProviderPayment.id.desc()).all()

    def create_provider_payment(
        self,
        payment_date: date,
        provider_id: int,
        amount: any,
        payment_mode: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ProviderPayment:
        amt = round_money(amount)
        if amt <= 0:
            raise ValueError("Payment amount must be greater than 0.")

        mode = payment_mode.upper()
        if mode not in ("CASH", "BANK"):
            raise ValueError("Payment mode must be CASH or BANK.")

        v_num = voucher_number.strip() if voucher_number else None
        if mode == "CASH" and not v_num:
            raise ValueError("Voucher number is required for CASH payments.")

        payment = ProviderPayment(
            payment_date=payment_date,
            provider_id=provider_id,
            amount=amt,
            payment_mode=mode,
            voucher_number=v_num,
            bank_reference=bank_reference.strip() if bank_reference else None,
            notes=notes.strip() if notes else None
        )
        self.session.add(payment)
        self.session.commit()
        self.session.refresh(payment)
        return payment

    def soft_delete_provider_payment(self, payment_id: int) -> bool:
        p = self.get_provider_payment_by_id(payment_id)
        if not p:
            return False
        p.soft_delete()
        self.session.commit()
        return True

    # --- Search Vouchers across both domains ---
    def search_voucher(self, voucher_number: str) -> Tuple[List[CustomerPayment], List[ProviderPayment]]:
        v_str = f"%{voucher_number.strip()}%"
        cust_payments = (
            self.session.query(CustomerPayment)
            .options(joinedload(CustomerPayment.customer))
            .filter(CustomerPayment.is_deleted == False, CustomerPayment.voucher_number.ilike(v_str))
            .all()
        )
        prov_payments = (
            self.session.query(ProviderPayment)
            .options(joinedload(ProviderPayment.provider))
            .filter(ProviderPayment.is_deleted == False, ProviderPayment.voucher_number.ilike(v_str))
            .all()
        )
        return cust_payments, prov_payments
