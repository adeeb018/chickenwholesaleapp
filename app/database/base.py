from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class TimestampMixin:
    """Mixin for record audit timestamps."""
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

class SoftDeleteMixin:
    """Mixin for safe soft deletion of financial and master records."""
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = utc_now()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
