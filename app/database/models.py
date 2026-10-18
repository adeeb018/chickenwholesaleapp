from sqlalchemy import (
    Column, Integer, String, Numeric, Date, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from app.database.base import Base, TimestampMixin, SoftDeleteMixin

class Customer(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    opening_balance = relationship(
        "CustomerOpeningBalance", uselist=False, back_populates="customer", cascade="all, delete-orphan", lazy="joined"
    )
    sales = relationship("Sale", back_populates="customer")
    payments = relationship("CustomerPayment", back_populates="customer")
    rate_adjustments = relationship(
        "CustomerRateAdjustment", back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Customer id={self.id} name='{self.name}'>"

class CustomerOpeningBalance(Base, TimestampMixin):
    __tablename__ = "customer_opening_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    as_of_date = Column(Date, nullable=False)
    notes = Column(String(255), nullable=True)

    customer = relationship("Customer", back_populates="opening_balance")

class Provider(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    opening_balance = relationship(
        "ProviderOpeningBalance", uselist=False, back_populates="provider", cascade="all, delete-orphan", lazy="joined"
    )
    purchases = relationship("Purchase", back_populates="provider")
    payments = relationship("ProviderPayment", back_populates="provider")

    def __repr__(self):
        return f"<Provider id={self.id} name='{self.name}'>"

class ProviderOpeningBalance(Base, TimestampMixin):
    __tablename__ = "provider_opening_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, unique=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    as_of_date = Column(Date, nullable=False)
    notes = Column(String(255), nullable=True)

    provider = relationship("Provider", back_populates="opening_balance")

class Item(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    purchases = relationship("Purchase", back_populates="item")
    sales = relationship("Sale", back_populates="item")

    def __repr__(self):
        return f"<Item id={self.id} name='{self.name}'>"

class Purchase(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_date = Column(Date, nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_type = Column(String(20), nullable=False)  # CASH / BANK
    voucher_number = Column(String(50), nullable=True, index=True)
    bank_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    provider = relationship("Provider", back_populates="purchases")
    item = relationship("Item", back_populates="purchases")

class Sale(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_date = Column(Date, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    gross_weight_kg = Column(Numeric(12, 3), nullable=False)
    box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    net_weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    total_amount = Column(Numeric(12, 2), nullable=False)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="sales")
    item = relationship("Item", back_populates="sales")

class CustomerPayment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customer_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_date = Column(Date, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_mode = Column(String(20), nullable=False)  # CASH / BANK
    voucher_number = Column(String(50), nullable=True, index=True)
    bank_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="payments")

class ProviderPayment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "provider_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_date = Column(Date, nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_mode = Column(String(20), nullable=False)  # CASH / BANK
    voucher_number = Column(String(50), nullable=True, index=True)
    bank_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    provider = relationship("Provider", back_populates="payments")

class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<AppSetting key='{self.key}' value='{self.value}'>"

class CustomerRateAdjustment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customer_rate_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    adjustment_per_kg = Column(Numeric(12, 2), nullable=False, default=0.00)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    days_of_week = Column(String(50), nullable=True, default="MON,TUE,WED,THU,FRI,SAT,SUN")
    notes = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    customer = relationship("Customer", back_populates="rate_adjustments")

    def __repr__(self):
        return f"<CustomerRateAdjustment id={self.id} customer_id={self.customer_id} adj={self.adjustment_per_kg} {self.start_date}->{self.end_date}>"

