from typing import List, Optional
from datetime import date
from app.database.connection import session_scope, get_session
from app.database.repositories.purchase_repository import PurchaseRepository
from app.database.models import Purchase

class PurchaseService:
    @staticmethod
    def get_purchases(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_id: Optional[int] = None,
        item_id: Optional[int] = None,
        payment_type: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[Purchase]:
        session = get_session()
        try:
            repo = PurchaseRepository(session)
            return repo.get_purchases(
                start_date=start_date,
                end_date=end_date,
                provider_id=provider_id,
                item_id=item_id,
                payment_type=payment_type,
                voucher_number=voucher_number
            )
        finally:
            session.close()

    @staticmethod
    def create_purchase(
        transaction_date: date,
        provider_id: int,
        item_id: int,
        weight_kg: any,
        rate_per_kg: any,
        payment_type: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Purchase:
        pay_type = payment_type.upper()
        if pay_type not in ("CASH", "BANK"):
            raise ValueError("Payment type must be CASH or BANK.")

        if pay_type == "CASH" and not (voucher_number and voucher_number.strip()):
            raise ValueError("Voucher number is required for CASH purchase payments.")

        with session_scope() as session:
            repo = PurchaseRepository(session)
            return repo.create(
                transaction_date=transaction_date,
                provider_id=provider_id,
                item_id=item_id,
                weight_kg=weight_kg,
                rate_per_kg=rate_per_kg,
                payment_type=pay_type,
                voucher_number=voucher_number,
                bank_reference=bank_reference,
                notes=notes
            )

    @staticmethod
    def update_purchase(
        purchase_id: int,
        transaction_date: date,
        provider_id: int,
        item_id: int,
        weight_kg: any,
        rate_per_kg: any,
        payment_type: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Purchase]:
        pay_type = payment_type.upper()
        if pay_type not in ("CASH", "BANK"):
            raise ValueError("Payment type must be CASH or BANK.")

        if pay_type == "CASH" and not (voucher_number and voucher_number.strip()):
            raise ValueError("Voucher number is required for CASH purchase payments.")

        with session_scope() as session:
            repo = PurchaseRepository(session)
            return repo.update(
                purchase_id=purchase_id,
                transaction_date=transaction_date,
                provider_id=provider_id,
                item_id=item_id,
                weight_kg=weight_kg,
                rate_per_kg=rate_per_kg,
                payment_type=pay_type,
                voucher_number=voucher_number,
                bank_reference=bank_reference,
                notes=notes
            )

    @staticmethod
    def soft_delete_purchase(purchase_id: int) -> bool:
        with session_scope() as session:
            repo = PurchaseRepository(session)
            return repo.soft_delete(purchase_id)
