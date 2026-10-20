from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session
from app.database.models import Customer, Provider, Sale, CustomerPayment, Purchase, ProviderPayment
from app.domain.accounting import generate_customer_ledger, generate_provider_ledger
from app.domain.models import CustomerStatement, ProviderStatement
from app.utils.decimal_utils import to_decimal, round_money

class BalanceService:
    @staticmethod
    def get_customer_statement(
        customer_id: int, start_date: date, end_date: date
    ) -> Optional[CustomerStatement]:
        session = get_session()
        try:
            customer = (
                session.query(Customer)
                .options(joinedload(Customer.opening_balance))
                .filter(Customer.id == customer_id, Customer.is_deleted == False)
                .first()
            )
            if not customer:
                return None

            initial_op_amt = customer.opening_balance.amount if customer.opening_balance else Decimal("0.00")
            initial_op_date = customer.opening_balance.as_of_date if customer.opening_balance else None

            all_sales = (
                session.query(Sale)
                .options(joinedload(Sale.item))
                .filter(Sale.customer_id == customer_id, Sale.is_deleted == False)
                .all()
            )
            all_payments = (
                session.query(CustomerPayment)
                .filter(CustomerPayment.customer_id == customer_id, CustomerPayment.is_deleted == False)
                .all()
            )
            from app.database.models import CustomerReturn
            all_returns = (
                session.query(CustomerReturn)
                .options(joinedload(CustomerReturn.lines))
                .filter(CustomerReturn.customer_id == customer_id, CustomerReturn.is_deleted == False)
                .all()
            )

            return generate_customer_ledger(
                customer_id=customer.id,
                customer_name=customer.name,
                phone=customer.phone,
                address=customer.address,
                initial_opening_balance=to_decimal(initial_op_amt),
                initial_opening_date=initial_op_date,
                all_sales=all_sales,
                all_payments=all_payments,
                start_date=start_date,
                end_date=end_date,
                all_returns=all_returns
            )
        finally:
            session.close()

    @staticmethod
    def get_provider_statement(
        provider_id: int, start_date: date, end_date: date
    ) -> Optional[ProviderStatement]:
        session = get_session()
        try:
            provider = (
                session.query(Provider)
                .options(joinedload(Provider.opening_balance))
                .filter(Provider.id == provider_id, Provider.is_deleted == False)
                .first()
            )
            if not provider:
                return None

            initial_op_amt = provider.opening_balance.amount if provider.opening_balance else Decimal("0.00")
            initial_op_date = provider.opening_balance.as_of_date if provider.opening_balance else None

            all_purchases = (
                session.query(Purchase)
                .options(joinedload(Purchase.item))
                .filter(Purchase.provider_id == provider_id, Purchase.is_deleted == False)
                .all()
            )
            all_payments = (
                session.query(ProviderPayment)
                .filter(ProviderPayment.provider_id == provider_id, ProviderPayment.is_deleted == False)
                .all()
            )

            return generate_provider_ledger(
                provider_id=provider.id,
                provider_name=provider.name,
                phone=provider.phone,
                address=provider.address,
                initial_opening_balance=to_decimal(initial_op_amt),
                initial_opening_date=initial_op_date,
                all_purchases=all_purchases,
                all_payments=all_payments,
                start_date=start_date,
                end_date=end_date
            )
        finally:
            session.close()

    @staticmethod
    def get_total_receivables(as_of_date: Optional[date] = None) -> Decimal:
        """Returns sum of all customer outstanding balances."""
        ref_date = as_of_date or date.today()
        session = get_session()
        try:
            customers = session.query(Customer).filter(Customer.is_deleted == False).all()
            total = Decimal("0.00")
            for c in customers:
                statement = BalanceService.get_customer_statement(c.id, date(2000, 1, 1), ref_date)
                if statement:
                    total += statement.closing_balance
            return round_money(total)
        finally:
            session.close()

    @staticmethod
    def get_total_payables(as_of_date: Optional[date] = None) -> Decimal:
        """Returns sum of all provider outstanding balances."""
        ref_date = as_of_date or date.today()
        session = get_session()
        try:
            providers = session.query(Provider).filter(Provider.is_deleted == False).all()
            total = Decimal("0.00")
            for p in providers:
                statement = BalanceService.get_provider_statement(p.id, date(2000, 1, 1), ref_date)
                if statement:
                    total += statement.closing_balance
            return round_money(total)
        finally:
            session.close()
