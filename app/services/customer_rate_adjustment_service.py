from datetime import date
from decimal import Decimal
from typing import Optional, Union, List, Tuple
from sqlalchemy.orm import joinedload
from app.database.connection import session_scope
from app.database.models import CustomerRateAdjustment, Customer
from app.services.setting_service import SettingService
from app.utils.decimal_utils import to_decimal, round_money

DAYS_OF_WEEK_LIST = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DAYS_OF_WEEK_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

class CustomerRateAdjustmentService:
    """
    Service for managing customer-specific differential rate adjustments
    across custom dates, date ranges, and days of the week.
    """

    @classmethod
    def create_adjustments_for_customers(
        cls,
        customer_ids: List[int],
        adjustment_per_kg: Union[Decimal, float, str, int],
        start_date: date,
        end_date: date,
        days_of_week: Optional[Union[str, List[str]]] = None,
        notes: Optional[str] = None
    ) -> List[CustomerRateAdjustment]:
        """
        Creates and persists rate adjustments for multiple customers in a single transaction.
        """
        if not customer_ids:
            raise ValueError("At least one customer must be selected.")
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date.")

        adj_dec = round_money(to_decimal(adjustment_per_kg))

        if isinstance(days_of_week, list):
            clean_days = ",".join(d.strip().upper() for d in days_of_week if d.strip().upper() in DAYS_OF_WEEK_LIST)
        elif isinstance(days_of_week, str) and days_of_week.strip():
            tokens = [t.strip().upper() for t in days_of_week.split(",") if t.strip().upper() in DAYS_OF_WEEK_LIST]
            clean_days = ",".join(tokens)
        else:
            clean_days = ",".join(DAYS_OF_WEEK_LIST)

        created_adjustments = []
        with session_scope() as session:
            valid_customers = session.query(Customer).filter(
                Customer.id.in_(customer_ids),
                Customer.deleted_at.is_(None)
            ).all()
            valid_ids = {c.id for c in valid_customers}

            for cid in customer_ids:
                if cid not in valid_ids:
                    continue
                adj = CustomerRateAdjustment(
                    customer_id=cid,
                    adjustment_per_kg=adj_dec,
                    start_date=start_date,
                    end_date=end_date,
                    days_of_week=clean_days,
                    notes=notes.strip() if notes else None,
                    is_active=True
                )
                session.add(adj)
                created_adjustments.append(adj)

            session.flush()
            for adj in created_adjustments:
                session.refresh(adj)

            return created_adjustments

    @classmethod
    def create_adjustment(
        cls,
        customer_id: int,
        adjustment_per_kg: Union[Decimal, float, str, int],
        start_date: date,
        end_date: date,
        days_of_week: Optional[Union[str, List[str]]] = None,
        notes: Optional[str] = None
    ) -> CustomerRateAdjustment:
        """
        Creates and persists a rate adjustment for a single customer.
        """
        results = cls.create_adjustments_for_customers(
            customer_ids=[customer_id],
            adjustment_per_kg=adjustment_per_kg,
            start_date=start_date,
            end_date=end_date,
            days_of_week=days_of_week,
            notes=notes
        )
        if not results:
            raise ValueError(f"Customer with ID {customer_id} does not exist.")
        return results[0]

    @classmethod
    def get_adjustments(cls, customer_id: Optional[int] = None, active_only: bool = False) -> List[CustomerRateAdjustment]:
        """
        Returns list of rate adjustments, optionally filtered by customer and active status.
        """
        with session_scope() as session:
            query = session.query(CustomerRateAdjustment).options(
                joinedload(CustomerRateAdjustment.customer)
            ).filter(CustomerRateAdjustment.deleted_at.is_(None))

            if customer_id:
                query = query.filter(CustomerRateAdjustment.customer_id == customer_id)
            if active_only:
                query = query.filter(CustomerRateAdjustment.is_active == True)

            return query.order_by(
                CustomerRateAdjustment.start_date.desc(),
                CustomerRateAdjustment.id.desc()
            ).all()

    @classmethod
    def get_adjustment_for_customer(cls, customer_id: int, target_date: date) -> Optional[CustomerRateAdjustment]:
        """
        Finds the applicable rate adjustment for a customer on a given transaction date.
        Takes into account date range, active status, and days of week.
        """
        day_code = DAYS_OF_WEEK_LIST[target_date.weekday()]

        with session_scope() as session:
            candidates = session.query(CustomerRateAdjustment).options(
                joinedload(CustomerRateAdjustment.customer)
            ).filter(
                CustomerRateAdjustment.customer_id == customer_id,
                CustomerRateAdjustment.deleted_at.is_(None),
                CustomerRateAdjustment.is_active == True,
                CustomerRateAdjustment.start_date <= target_date,
                CustomerRateAdjustment.end_date >= target_date
            ).order_by(
                CustomerRateAdjustment.id.desc()
            ).all()

            for cand in candidates:
                if not cand.days_of_week:
                    return cand
                allowed_days = [d.strip().upper() for d in cand.days_of_week.split(",")]
                if day_code in allowed_days:
                    return cand

            return None

    @classmethod
    def get_effective_rate_for_customer(
        cls, customer_id: int, target_date: date
    ) -> Tuple[Decimal, Optional[CustomerRateAdjustment], Decimal]:
        """
        Calculates the effective selling rate for a customer on a transaction date.
        Returns: (effective_rate, matched_adjustment, benchmark_main_rate)
        """
        main_rate = SettingService.get_main_chicken_rate()
        adj = cls.get_adjustment_for_customer(customer_id, target_date)

        if adj:
            effective = max(Decimal("0.00"), main_rate + adj.adjustment_per_kg)
            return effective, adj, main_rate
        else:
            return main_rate, None, main_rate

    @classmethod
    def delete_adjustment(cls, adjustment_id: int) -> bool:
        """Soft-deletes a specific rate adjustment."""
        with session_scope() as session:
            adj = session.query(CustomerRateAdjustment).filter(
                CustomerRateAdjustment.id == adjustment_id,
                CustomerRateAdjustment.deleted_at.is_(None)
            ).first()
            if adj:
                adj.soft_delete()
                adj.is_active = False
                return True
            return False

    @classmethod
    def delete_adjustments_for_customer(cls, customer_id: int) -> int:
        """Soft-deletes all active adjustments for a given customer."""
        with session_scope() as session:
            adjs = session.query(CustomerRateAdjustment).filter(
                CustomerRateAdjustment.customer_id == customer_id,
                CustomerRateAdjustment.deleted_at.is_(None)
            ).all()
            if not adjs:
                return 0
            count = 0
            for a in adjs:
                a.soft_delete()
                a.is_active = False
                count += 1
            return count
