from typing import List, Optional
from datetime import date
from app.database.connection import session_scope, get_session
from app.database.repositories.sales_repository import SalesRepository
from app.database.models import Sale

class SalesService:
    @staticmethod
    def get_sales(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        item_id: Optional[int] = None
    ) -> List[Sale]:
        session = get_session()
        try:
            repo = SalesRepository(session)
            return repo.get_sales(
                start_date=start_date,
                end_date=end_date,
                customer_id=customer_id,
                item_id=item_id
            )
        finally:
            session.close()

    @staticmethod
    def get_sale_by_id(sale_id: int) -> Optional[Sale]:
        session = get_session()
        try:
            repo = SalesRepository(session)
            return repo.get_by_id(sale_id)
        finally:
            session.close()

    @staticmethod
    def create_sale(
        transaction_date: date,
        customer_id: int,
        item_id: int,
        gross_weight_kg: any,
        box_weight_kg: any,
        rate_per_kg: any,
        discount_amount: any = 0.00,
        box_count: int = 0,
        notes: Optional[str] = None,
        allocations: Optional[list] = None,
        batch_id: Optional[int] = None
    ) -> Sale:
        with session_scope() as session:
            repo = SalesRepository(session)
            return repo.create(
                transaction_date=transaction_date,
                customer_id=customer_id,
                item_id=item_id,
                gross_weight_kg=gross_weight_kg,
                box_weight_kg=box_weight_kg,
                rate_per_kg=rate_per_kg,
                discount_amount=discount_amount,
                box_count=box_count,
                notes=notes,
                allocations=allocations,
                batch_id=batch_id
            )

    @staticmethod
    def update_sale(
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
        with session_scope() as session:
            repo = SalesRepository(session)
            return repo.update(
                sale_id=sale_id,
                transaction_date=transaction_date,
                customer_id=customer_id,
                item_id=item_id,
                gross_weight_kg=gross_weight_kg,
                box_weight_kg=box_weight_kg,
                rate_per_kg=rate_per_kg,
                discount_amount=discount_amount,
                box_count=box_count,
                notes=notes
            )

    @staticmethod
    def soft_delete_sale(sale_id: int) -> bool:
        with session_scope() as session:
            repo = SalesRepository(session)
            return repo.soft_delete(sale_id)
