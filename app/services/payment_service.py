from typing import List, Optional, Tuple
from datetime import date
from app.database.connection import session_scope, get_session
from app.database.repositories.payment_repository import PaymentRepository
from app.database.models import CustomerPayment, ProviderPayment

class PaymentService:
    # --- Customer Payments ---
    @staticmethod
    def get_customer_payments(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        payment_mode: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[CustomerPayment]:
        session = get_session()
        try:
            repo = PaymentRepository(session)
            return repo.get_customer_payments(
                start_date=start_date,
                end_date=end_date,
                customer_id=customer_id,
                payment_mode=payment_mode,
                voucher_number=voucher_number
            )
        finally:
            session.close()

    @staticmethod
    def create_customer_payment(
        payment_date: date,
        customer_id: int,
        amount: any,
        payment_mode: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CustomerPayment:
        with session_scope() as session:
            repo = PaymentRepository(session)
            return repo.create_customer_payment(
                payment_date=payment_date,
                customer_id=customer_id,
                amount=amount,
                payment_mode=payment_mode,
                voucher_number=voucher_number,
                bank_reference=bank_reference,
                notes=notes
            )

    @staticmethod
    def soft_delete_customer_payment(payment_id: int) -> bool:
        with session_scope() as session:
            repo = PaymentRepository(session)
            return repo.soft_delete_customer_payment(payment_id)

    # --- Provider Payments ---
    @staticmethod
    def get_provider_payments(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_id: Optional[int] = None,
        payment_mode: Optional[str] = None,
        voucher_number: Optional[str] = None
    ) -> List[ProviderPayment]:
        session = get_session()
        try:
            repo = PaymentRepository(session)
            return repo.get_provider_payments(
                start_date=start_date,
                end_date=end_date,
                provider_id=provider_id,
                payment_mode=payment_mode,
                voucher_number=voucher_number
            )
        finally:
            session.close()

    @staticmethod
    def create_provider_payment(
        payment_date: date,
        provider_id: int,
        amount: any,
        payment_mode: str,
        voucher_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ProviderPayment:
        with session_scope() as session:
            repo = PaymentRepository(session)
            return repo.create_provider_payment(
                payment_date=payment_date,
                provider_id=provider_id,
                amount=amount,
                payment_mode=payment_mode,
                voucher_number=voucher_number,
                bank_reference=bank_reference,
                notes=notes
            )

    @staticmethod
    def soft_delete_provider_payment(payment_id: int) -> bool:
        with session_scope() as session:
            repo = PaymentRepository(session)
            return repo.soft_delete_provider_payment(payment_id)

    # --- Search Vouchers ---
    @staticmethod
    def search_voucher(voucher_number: str) -> Tuple[List[CustomerPayment], List[ProviderPayment]]:
        session = get_session()
        try:
            repo = PaymentRepository(session)
            return repo.search_voucher(voucher_number)
        finally:
            session.close()
