from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

@dataclass
class CustomerOpeningBalanceDTO:
    customer_id: int
    amount: Decimal
    as_of_date: date
    notes: Optional[str] = None

@dataclass
class ProviderOpeningBalanceDTO:
    provider_id: int
    amount: Decimal
    as_of_date: date
    notes: Optional[str] = None

@dataclass
class LedgerEntry:
    entry_date: date
    transaction_type: str  # "OPENING_BALANCE", "SALE", "PURCHASE", "PAYMENT_RECEIVED", "PAYMENT_MADE"
    reference_id: Optional[int]
    description: str
    debit: Decimal       # Increase in receivable (Sale) or decrease in payable (Payment made)
    credit: Decimal      # Decrease in receivable (Payment received) or increase in payable (Purchase)
    running_balance: Decimal
    voucher_number: Optional[str] = None
    item_name: Optional[str] = None
    net_weight_kg: Optional[Decimal] = None
    rate_per_kg: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None

@dataclass
class CustomerStatement:
    customer_id: int
    customer_name: str
    phone: Optional[str]
    address: Optional[str]
    start_date: date
    end_date: date
    period_opening_balance: Decimal
    total_net_weight_kg: Decimal
    total_sales_amount: Decimal
    total_cash_payments: Decimal
    total_bank_payments: Decimal
    total_payments: Decimal
    closing_balance: Decimal
    ledger_entries: List[LedgerEntry]

@dataclass
class ProviderStatement:
    provider_id: int
    provider_name: str
    phone: Optional[str]
    address: Optional[str]
    start_date: date
    end_date: date
    period_opening_balance: Decimal
    total_purchase_weight_kg: Decimal
    total_purchases_amount: Decimal
    total_cash_payments: Decimal
    total_bank_payments: Decimal
    total_payments: Decimal
    closing_balance: Decimal
    ledger_entries: List[LedgerEntry]

@dataclass
class WeightLossSummary:
    start_date: date
    end_date: date
    total_purchased_kg: Decimal
    total_sales_gross_kg: Decimal
    total_sales_box_kg: Decimal
    total_sales_net_kg: Decimal
    weight_loss_kg: Decimal
    weight_loss_percentage: Decimal
