from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.models import Item

class ItemRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, include_inactive: bool = False) -> List[Item]:
        query = self.session.query(Item).filter(Item.is_deleted == False)
        if not include_inactive:
            query = query.filter(Item.is_active == True)
        return query.order_by(Item.name.asc()).all()

    def get_by_id(self, item_id: int) -> Optional[Item]:
        return (
            self.session.query(Item)
            .filter(Item.id == item_id, Item.is_deleted == False)
            .first()
        )

    def create(self, name: str, code: Optional[str] = None) -> Item:
        item = Item(
            name=name.strip(),
            code=code.strip() if code else None,
            is_active=True
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def update(
        self,
        item_id: int,
        name: str,
        code: Optional[str] = None,
        is_active: bool = True
    ) -> Optional[Item]:
        item = self.get_by_id(item_id)
        if not item:
            return None
        item.name = name.strip()
        item.code = code.strip() if code else None
        item.is_active = is_active
        self.session.commit()
        self.session.refresh(item)
        return item

    def soft_delete(self, item_id: int) -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        item.soft_delete()
        self.session.commit()
        return True
