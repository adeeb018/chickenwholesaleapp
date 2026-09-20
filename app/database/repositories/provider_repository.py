from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.database.models import Provider, ProviderOpeningBalance
from app.utils.decimal_utils import to_decimal

class ProviderRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, include_inactive: bool = False) -> List[Provider]:
        query = (
            self.session.query(Provider)
            .options(joinedload(Provider.opening_balance))
            .filter(Provider.is_deleted == False)
        )
        if not include_inactive:
            query = query.filter(Provider.is_active == True)
        return query.order_by(Provider.name.asc()).all()

    def get_by_id(self, provider_id: int) -> Optional[Provider]:
        return (
            self.session.query(Provider)
            .options(joinedload(Provider.opening_balance))
            .filter(Provider.id == provider_id, Provider.is_deleted == False)
            .first()
        )

    def search(self, query_str: str) -> List[Provider]:
        pattern = f"%{query_str}%"
        return (
            self.session.query(Provider)
            .options(joinedload(Provider.opening_balance))
            .filter(
                Provider.is_deleted == False,
                (Provider.name.ilike(pattern) | Provider.phone.ilike(pattern))
            )
            .order_by(Provider.name.asc())
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
    ) -> Provider:
        provider = Provider(
            name=name.strip(),
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            notes=notes.strip() if notes else None,
            is_active=True
        )
        self.session.add(provider)
        self.session.flush()

        if opening_balance is not None or opening_balance_date is not None:
            op_date = opening_balance_date or date.today()
            op_amt = to_decimal(opening_balance or 0)
            op = ProviderOpeningBalance(
                provider_id=provider.id,
                amount=op_amt,
                as_of_date=op_date,
                notes="Initial Opening Balance"
            )
            self.session.add(op)

        self.session.commit()
        self.session.refresh(provider)
        return provider

    def update(
        self,
        provider_id: int,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_active: bool = True,
        opening_balance: Optional[any] = None,
        opening_balance_date: Optional[date] = None
    ) -> Optional[Provider]:
        provider = self.get_by_id(provider_id)
        if not provider:
            return None

        provider.name = name.strip()
        provider.phone = phone.strip() if phone else None
        provider.address = address.strip() if address else None
        provider.notes = notes.strip() if notes else None
        provider.is_active = is_active

        if opening_balance is not None or opening_balance_date is not None:
            op_amt = to_decimal(opening_balance or 0)
            op_date = opening_balance_date or date.today()

            if provider.opening_balance:
                provider.opening_balance.amount = op_amt
                provider.opening_balance.as_of_date = op_date
            else:
                op = ProviderOpeningBalance(
                    provider_id=provider.id,
                    amount=op_amt,
                    as_of_date=op_date,
                    notes="Initial Opening Balance"
                )
                self.session.add(op)

        self.session.commit()
        self.session.refresh(provider)
        return provider

    def soft_delete(self, provider_id: int) -> bool:
        provider = self.get_by_id(provider_id)
        if not provider:
            return False
        provider.soft_delete()
        self.session.commit()
        return True
