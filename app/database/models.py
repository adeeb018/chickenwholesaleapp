from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text, Boolean
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
    returns = relationship("CustomerReturn", back_populates="customer")
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
    box_count = Column(Integer, nullable=False, default=0)
    gross_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    net_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_type = Column(String(20), nullable=False)  # CASH / BANK
    voucher_number = Column(String(50), nullable=True, index=True)
    bank_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    provider = relationship("Provider", back_populates="purchases")
    item = relationship("Item", back_populates="purchases")
    batch = relationship("PurchaseBatch", uselist=False, back_populates="purchase", lazy="joined")

class Sale(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_date = Column(Date, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    box_count = Column(Integer, nullable=False, default=0)
    gross_weight_kg = Column(Numeric(12, 3), nullable=False)
    box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    net_weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    total_amount = Column(Numeric(12, 2), nullable=False)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="sales")
    item = relationship("Item", back_populates="sales")
    allocations = relationship("SaleBatchAllocation", back_populates="sale", cascade="all, delete-orphan", lazy="joined")
    returns = relationship("CustomerReturn", back_populates="original_sale")

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

class PurchaseBatch(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "purchase_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_number = Column(String(100), nullable=False, unique=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    purchase_date = Column(Date, nullable=False, index=True)
    gross_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    box_count = Column(Integer, nullable=False, default=0)
    net_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    current_stock_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)  # ACTIVE, DEPLETED, CLOSED
    closed_at = Column(DateTime, nullable=True)
    closed_notes = Column(Text, nullable=True)

    # Relationships
    purchase = relationship("Purchase", back_populates="batch")
    item = relationship("Item")
    allocations = relationship("SaleBatchAllocation", back_populates="batch")
    movements = relationship("InventoryMovement", back_populates="batch", cascade="all, delete-orphan")
    reconciliations = relationship("DailyStockReconciliation", back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PurchaseBatch id={self.id} num='{self.batch_number}' stock={self.current_stock_kg} status={self.status}>"

class SaleBatchAllocation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sale_batch_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("purchase_batches.id"), nullable=False, index=True)
    gross_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    box_count = Column(Integer, nullable=False, default=0)
    net_weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    sale = relationship("Sale", back_populates="allocations")
    batch = relationship("PurchaseBatch", back_populates="allocations")
    return_lines = relationship("CustomerReturnLine", back_populates="sale_allocation")

    def __repr__(self):
        return f"<SaleBatchAllocation id={self.id} sale_id={self.sale_id} batch_id={self.batch_id} net={self.net_weight_kg}>"

class InventoryMovement(Base, TimestampMixin):
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("purchase_batches.id"), nullable=False, index=True)
    movement_type = Column(String(30), nullable=False, index=True)
    # PURCHASE, SALE, CUSTOMER_RETURN, STOCK_LOSS, STOCK_GAIN, STOCK_ADJUSTMENT
    quantity_kg = Column(Numeric(12, 3), nullable=False)
    business_date = Column(Date, nullable=False, index=True)
    reference_type = Column(String(50), nullable=True)  # PURCHASE, SALE, CUSTOMER_RETURN, RECONCILIATION, BATCH_CLOSURE
    reference_id = Column(Integer, nullable=True, index=True)
    reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    batch = relationship("PurchaseBatch", back_populates="movements")

    def __repr__(self):
        return f"<InventoryMovement id={self.id} batch_id={self.batch_id} type={self.movement_type} qty={self.quantity_kg}>"

class DailyStockReconciliation(Base, TimestampMixin):
    __tablename__ = "daily_stock_reconciliations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("purchase_batches.id"), nullable=False, index=True)
    business_date = Column(Date, nullable=False, index=True)
    opening_stock_kg = Column(Numeric(12, 3), nullable=False)
    stock_additions_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    sales_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    returns_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    other_adjustments_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    calculated_closing_kg = Column(Numeric(12, 3), nullable=False)
    actual_closing_kg = Column(Numeric(12, 3), nullable=False)
    difference_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    status = Column(String(30), nullable=False, default="RECONCILED")  # RECONCILED, CORRECTED
    reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    batch = relationship("PurchaseBatch", back_populates="reconciliations")

    def __repr__(self):
        return f"<DailyStockReconciliation id={self.id} batch_id={self.batch_id} date={self.business_date} diff={self.difference_kg}>"

class CustomerReturn(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customer_returns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    return_number = Column(String(50), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    original_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    return_date = Column(Date, nullable=False, index=True)
    total_returned_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    financial_credit_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="returns")
    original_sale = relationship("Sale", back_populates="returns")
    lines = relationship("CustomerReturnLine", back_populates="customer_return", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CustomerReturn id={self.id} num='{self.return_number}' cust={self.customer_id} weight={self.total_returned_weight_kg}>"

class CustomerReturnLine(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customer_return_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_return_id = Column(Integer, ForeignKey("customer_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_batch_allocation_id = Column(Integer, ForeignKey("sale_batch_allocations.id"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("purchase_batches.id"), nullable=False, index=True)
    box_count = Column(Integer, nullable=False, default=0)
    returned_gross_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    returned_box_weight_kg = Column(Numeric(12, 3), nullable=False, default=0.000)
    returned_net_weight_kg = Column(Numeric(12, 3), nullable=False)
    rate_per_kg = Column(Numeric(12, 2), nullable=False)
    financial_amount = Column(Numeric(12, 2), nullable=False)
    resale_eligible = Column(Boolean, nullable=False, default=True)
    reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    customer_return = relationship("CustomerReturn", back_populates="lines")
    sale_allocation = relationship("SaleBatchAllocation", back_populates="return_lines")
    batch = relationship("PurchaseBatch")

    def __repr__(self):
        return f"<CustomerReturnLine id={self.id} return_id={self.customer_return_id} batch_id={self.batch_id} net={self.returned_net_weight_kg}>"


