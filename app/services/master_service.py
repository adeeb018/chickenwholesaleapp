from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from app.database.connection import session_scope, get_session
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.provider_repository import ProviderRepository
from app.database.repositories.item_repository import ItemRepository
from app.database.models import Customer, Provider, Item

class MasterService:
    # --- Customer Management ---
    @staticmethod
    def get_all_customers(include_inactive: bool = False) -> List[Customer]:
        with session_scope() as session:
            repo = CustomerRepository(session)
            return repo.get_all(include_inactive=include_inactive)

    @staticmethod
    def get_customer_by_id(customer_id: int) -> Optional[Customer]:
        session = get_session()
        try:
            repo = CustomerRepository(session)
            return repo.get_by_id(customer_id)
        finally:
            session.close()

    @staticmethod
    def create_customer(
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Customer:
        with session_scope() as session:
            repo = CustomerRepository(session)
            return repo.create(
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                opening_balance=opening_balance,
                opening_balance_date=opening_balance_date
            )

    @staticmethod
    def update_customer(
        customer_id: int,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_active: bool = True,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Optional[Customer]:
        with session_scope() as session:
            repo = CustomerRepository(session)
            return repo.update(
                customer_id=customer_id,
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                is_active=is_active,
                opening_balance=opening_balance,
                opening_balance_date=opening_balance_date
            )

    @staticmethod
    def soft_delete_customer(customer_id: int) -> bool:
        with session_scope() as session:
            repo = CustomerRepository(session)
            return repo.soft_delete(customer_id)

    # --- Provider Management ---
    @staticmethod
    def get_all_providers(include_inactive: bool = False) -> List[Provider]:
        with session_scope() as session:
            repo = ProviderRepository(session)
            return repo.get_all(include_inactive=include_inactive)

    @staticmethod
    def get_provider_by_id(provider_id: int) -> Optional[Provider]:
        session = get_session()
        try:
            repo = ProviderRepository(session)
            return repo.get_by_id(provider_id)
        finally:
            session.close()

    @staticmethod
    def create_provider(
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Provider:
        with session_scope() as session:
            repo = ProviderRepository(session)
            return repo.create(
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                opening_balance=opening_balance,
                opening_balance_date=opening_balance_date
            )

    @staticmethod
    def update_provider(
        provider_id: int,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_active: bool = True,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Optional[Provider]:
        with session_scope() as session:
            repo = ProviderRepository(session)
            return repo.update(
                provider_id=provider_id,
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                is_active=is_active,
                opening_balance=opening_balance,
                opening_balance_date=opening_balance_date
            )

    @staticmethod
    def soft_delete_provider(provider_id: int) -> bool:
        with session_scope() as session:
            repo = ProviderRepository(session)
            return repo.soft_delete(provider_id)

    # --- Item Management ---
    @staticmethod
    def get_all_items(include_inactive: bool = False) -> List[Item]:
        with session_scope() as session:
            repo = ItemRepository(session)
            return repo.get_all(include_inactive=include_inactive)

    @staticmethod
    def create_item(name: str, code: Optional[str] = None) -> Item:
        with session_scope() as session:
            repo = ItemRepository(session)
            return repo.create(name=name, code=code)

    @staticmethod
    def update_item(item_id: int, name: str, code: Optional[str] = None, is_active: bool = True) -> Optional[Item]:
        with session_scope() as session:
            repo = ItemRepository(session)
            return repo.update(item_id=item_id, name=name, code=code, is_active=is_active)

    @staticmethod
    def soft_delete_item(item_id: int) -> bool:
        with session_scope() as session:
            repo = ItemRepository(session)
            return repo.soft_delete(item_id)
