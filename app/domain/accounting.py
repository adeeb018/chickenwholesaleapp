from datetime import date
from decimal import Decimal
from typing import List, Optional
from app.utils.decimal_utils import round_money, round_weight, to_decimal, format_weight
from app.domain.models import LedgerEntry, CustomerStatement, ProviderStatement

def calculate_customer_period_opening_balance(
    initial_opening_balance: Decimal,
    initial_opening_date: Optional[date],
    prior_sales: List[any],
    prior_payments: List[any],
    period_start_date: date,
    prior_returns: Optional[List[any]] = None
) -> Decimal:
    """
    Calculates customer opening balance as of period_start_date.
    Includes initial opening balance (if initial_opening_date < period_start_date or equal)
    plus all sales prior to period_start_date minus all payments and customer returns prior to period_start_date.
    """
    running = Decimal("0.00")
    
    # Add initial opening balance if it applies prior to or on the start date
    if initial_opening_balance:
        running += to_decimal(initial_opening_balance)
        
    for sale in prior_sales:
        if sale.transaction_date < period_start_date:
            running += to_decimal(sale.total_amount)
            
    for pymt in prior_payments:
        if pymt.payment_date < period_start_date:
            running -= to_decimal(pymt.amount)

    if prior_returns:
        for ret in prior_returns:
            if ret.return_date < period_start_date:
                running -= to_decimal(ret.financial_credit_amount)
            
    return round_money(running)

def calculate_provider_period_opening_balance(
    initial_opening_balance: Decimal,
    initial_opening_date: Optional[date],
    prior_purchases: List[any],
    prior_payments: List[any],
    period_start_date: date
) -> Decimal:
    """
    Calculates provider opening balance (amount payable to provider) as of period_start_date.
    Opening Balance + Purchases prior to start_date - Payments prior to start_date.
    """
    running = Decimal("0.00")
    
    if initial_opening_balance:
        running += to_decimal(initial_opening_balance)
        
    for purchase in prior_purchases:
        if purchase.transaction_date < period_start_date:
            running += to_decimal(purchase.total_amount)
            
    for pymt in prior_payments:
        if pymt.payment_date < period_start_date:
            running -= to_decimal(pymt.amount)
            
    return round_money(running)

def generate_customer_ledger(
    customer_id: int,
    customer_name: str,
    phone: Optional[str],
    address: Optional[str],
    initial_opening_balance: Decimal,
    initial_opening_date: Optional[date],
    all_sales: List[any],
    all_payments: List[any],
    start_date: date,
    end_date: date,
    all_returns: Optional[List[any]] = None
) -> CustomerStatement:
    """
    Generates a full Customer Statement with period opening balance,
    chronological ledger entries within start_date..end_date, and closing balance.
    """
    returns_list = all_returns or []

    # 1. Filter prior transactions vs period transactions
    prior_sales = [s for s in all_sales if s.transaction_date < start_date]
    period_sales = [s for s in all_sales if start_date <= s.transaction_date <= end_date]
    
    prior_payments = [p for p in all_payments if p.payment_date < start_date]
    period_payments = [p for p in all_payments if start_date <= p.payment_date <= end_date]

    prior_returns = [r for r in returns_list if r.return_date < start_date]
    period_returns = [r for r in returns_list if start_date <= r.return_date <= end_date]

    # 2. Compute opening balance at start_date
    period_opening = calculate_customer_period_opening_balance(
        initial_opening_balance=initial_opening_balance,
        initial_opening_date=initial_opening_date,
        prior_sales=prior_sales,
        prior_payments=prior_payments,
        period_start_date=start_date,
        prior_returns=prior_returns
    )

    # 3. Build combined event stream for period
    events = []
    for s in period_sales:
        events.append({
            "date": s.transaction_date,
            "type": "SALE",
            "obj": s,
            "sort_id": s.id
        })
    for r in period_returns:
        events.append({
            "date": r.return_date,
            "type": "CUSTOMER_RETURN",
            "obj": r,
            "sort_id": r.id
        })
    for p in period_payments:
        events.append({
            "date": p.payment_date,
            "type": "PAYMENT_RECEIVED",
            "obj": p,
            "sort_id": p.id
        })

    # Sort events chronologically by date, then type (Sale before Return before Payment on same day), then ID
    def event_order(t):
        if t == "SALE":
            return 0
        elif t == "CUSTOMER_RETURN":
            return 1
        return 2

    events.sort(key=lambda x: (x["date"], event_order(x["type"]), x["sort_id"]))

    ledger_entries: List[LedgerEntry] = []
    running_balance = period_opening

    # Add explicit Opening Balance ledger row
    ledger_entries.append(
        LedgerEntry(
            entry_date=start_date,
            transaction_type="OPENING_BALANCE",
            reference_id=None,
            description="Opening Balance as of " + start_date.strftime("%d/%m/%Y"),
            debit=Decimal("0.00"),
            credit=Decimal("0.00"),
            running_balance=running_balance
        )
    )

    total_net_weight = Decimal("0.000")
    total_sales_amount = Decimal("0.00")
    total_cash_payments = Decimal("0.00")
    total_bank_payments = Decimal("0.00")
    total_returns_amount = Decimal("0.00")
    total_returns_weight = Decimal("0.000")

    for ev in events:
        if ev["type"] == "SALE":
            s = ev["obj"]
            amt = round_money(s.total_amount)
            net_w = round_weight(s.net_weight_kg)
            rate = round_money(s.rate_per_kg)
            
            running_balance += amt
            total_net_weight += net_w
            total_sales_amount += amt

            item_name = s.item.name if hasattr(s, "item") and s.item else "Chicken"
            disc = round_money(getattr(s, "discount_amount", Decimal("0.00")))
            desc = f"Sale ({item_name} - {net_w} KG @ ₹{rate}/KG)"
            if disc > 0:
                desc += f" [Disc: ₹{disc}]"
            if s.notes:
                desc += f" [{s.notes}]"

            ledger_entries.append(
                LedgerEntry(
                    entry_date=s.transaction_date,
                    transaction_type="SALE",
                    reference_id=s.id,
                    description=desc,
                    debit=amt,
                    credit=Decimal("0.00"),
                    running_balance=round_money(running_balance),
                    item_name=item_name,
                    net_weight_kg=net_w,
                    rate_per_kg=rate,
                    discount_amount=disc
                )
            )
        elif ev["type"] == "CUSTOMER_RETURN":
            r = ev["obj"]
            amt = round_money(r.financial_credit_amount)
            net_w = round_weight(r.total_returned_weight_kg)
            running_balance -= amt
            total_returns_amount += amt
            total_returns_weight += net_w

            desc = f"Customer Return #{r.return_number} ({format_weight(net_w)})"
            if r.notes:
                desc += f" [{r.notes}]"

            ledger_entries.append(
                LedgerEntry(
                    entry_date=r.return_date,
                    transaction_type="CUSTOMER_RETURN",
                    reference_id=r.id,
                    description=desc,
                    debit=Decimal("0.00"),
                    credit=amt,
                    running_balance=round_money(running_balance),
                    net_weight_kg=net_w
                )
            )
        elif ev["type"] == "PAYMENT_RECEIVED":
            p = ev["obj"]
            amt = round_money(p.amount)
            running_balance -= amt

            if p.payment_mode == "CASH":
                total_cash_payments += amt
                desc = f"Payment Received (CASH) - Voucher #{p.voucher_number or 'N/A'}"
            else:
                total_bank_payments += amt
                desc = f"Payment Received (BANK)"
                if p.bank_reference:
                    desc += f" - Ref: {p.bank_reference}"

            if p.notes:
                desc += f" [{p.notes}]"

            ledger_entries.append(
                LedgerEntry(
                    entry_date=p.payment_date,
                    transaction_type="PAYMENT_RECEIVED",
                    reference_id=p.id,
                    description=desc,
                    debit=Decimal("0.00"),
                    credit=amt,
                    running_balance=round_money(running_balance),
                    voucher_number=p.voucher_number
                )
            )

    total_payments = total_cash_payments + total_bank_payments
    closing_balance = round_money(running_balance)

    return CustomerStatement(
        customer_id=customer_id,
        customer_name=customer_name,
        phone=phone,
        address=address,
        start_date=start_date,
        end_date=end_date,
        period_opening_balance=period_opening,
        total_net_weight_kg=round_weight(total_net_weight),
        total_sales_amount=round_money(total_sales_amount),
        total_cash_payments=round_money(total_cash_payments),
        total_bank_payments=round_money(total_bank_payments),
        total_payments=round_money(total_payments),
        closing_balance=closing_balance,
        ledger_entries=ledger_entries,
        total_returns_amount=round_money(total_returns_amount),
        total_returns_weight_kg=round_weight(total_returns_weight)
    )

def generate_provider_ledger(
    provider_id: int,
    provider_name: str,
    phone: Optional[str],
    address: Optional[str],
    initial_opening_balance: Decimal,
    initial_opening_date: Optional[date],
    all_purchases: List[any],
    all_payments: List[any],
    start_date: date,
    end_date: date
) -> ProviderStatement:
    """
    Generates a full Provider Statement with period opening balance,
    chronological ledger entries within start_date..end_date, and closing balance.
    """
    prior_purchases = [p for p in all_purchases if p.transaction_date < start_date]
    period_purchases = [p for p in all_purchases if start_date <= p.transaction_date <= end_date]

    prior_payments = [p for p in all_payments if p.payment_date < start_date]
    period_payments = [p for p in all_payments if start_date <= p.payment_date <= end_date]

    period_opening = calculate_provider_period_opening_balance(
        initial_opening_balance=initial_opening_balance,
        initial_opening_date=initial_opening_date,
        prior_purchases=prior_purchases,
        prior_payments=prior_payments,
        period_start_date=start_date
    )

    events = []
    for pur in period_purchases:
        events.append({
            "date": pur.transaction_date,
            "type": "PURCHASE",
            "obj": pur,
            "sort_id": pur.id
        })
    for p in period_payments:
        events.append({
            "date": p.payment_date,
            "type": "PAYMENT_MADE",
            "obj": p,
            "sort_id": p.id
        })

    events.sort(key=lambda x: (x["date"], 0 if x["type"] == "PURCHASE" else 1, x["sort_id"]))

    ledger_entries: List[LedgerEntry] = []
    running_balance = period_opening

    ledger_entries.append(
        LedgerEntry(
            entry_date=start_date,
            transaction_type="OPENING_BALANCE",
            reference_id=None,
            description="Opening Balance as of " + start_date.strftime("%d/%m/%Y"),
            debit=Decimal("0.00"),
            credit=Decimal("0.00"),
            running_balance=running_balance
        )
    )

    total_weight = Decimal("0.000")
    total_purchases_amount = Decimal("0.00")
    total_cash_payments = Decimal("0.00")
    total_bank_payments = Decimal("0.00")

    for ev in events:
        if ev["type"] == "PURCHASE":
            pur = ev["obj"]
            amt = round_money(pur.total_amount)
            wt = round_weight(pur.weight_kg)
            rate = round_money(pur.rate_per_kg)
            
            running_balance += amt
            total_weight += wt
            total_purchases_amount += amt

            item_name = pur.item.name if hasattr(pur, "item") and pur.item else "Chicken"
            desc = f"Purchase ({item_name} - {wt} KG @ ₹{rate}/KG)"
            if pur.voucher_number:
                desc += f" Voucher #{pur.voucher_number}"
            if pur.notes:
                desc += f" [{pur.notes}]"

            ledger_entries.append(
                LedgerEntry(
                    entry_date=pur.transaction_date,
                    transaction_type="PURCHASE",
                    reference_id=pur.id,
                    description=desc,
                    debit=Decimal("0.00"),
                    credit=amt,
                    running_balance=round_money(running_balance),
                    voucher_number=pur.voucher_number,
                    item_name=item_name,
                    net_weight_kg=wt,
                    rate_per_kg=rate
                )
            )
        elif ev["type"] == "PAYMENT_MADE":
            p = ev["obj"]
            amt = round_money(p.amount)
            running_balance -= amt

            if p.payment_mode == "CASH":
                total_cash_payments += amt
                desc = f"Payment Made (CASH) - Voucher #{p.voucher_number or 'N/A'}"
            else:
                total_bank_payments += amt
                desc = f"Payment Made (BANK)"
                if p.bank_reference:
                    desc += f" - Ref: {p.bank_reference}"

            if p.notes:
                desc += f" [{p.notes}]"

            ledger_entries.append(
                LedgerEntry(
                    entry_date=p.payment_date,
                    transaction_type="PAYMENT_MADE",
                    reference_id=p.id,
                    description=desc,
                    debit=amt,
                    credit=Decimal("0.00"),
                    running_balance=round_money(running_balance),
                    voucher_number=p.voucher_number
                )
            )

    total_payments = total_cash_payments + total_bank_payments
    closing_balance = round_money(running_balance)

    return ProviderStatement(
        provider_id=provider_id,
        provider_name=provider_name,
        phone=phone,
        address=address,
        start_date=start_date,
        end_date=end_date,
        period_opening_balance=period_opening,
        total_purchase_weight_kg=round_weight(total_weight),
        total_purchases_amount=round_money(total_purchases_amount),
        total_cash_payments=round_money(total_cash_payments),
        total_bank_payments=round_money(total_bank_payments),
        total_payments=round_money(total_payments),
        closing_balance=closing_balance,
        ledger_entries=ledger_entries
    )
