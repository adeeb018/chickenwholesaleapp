from datetime import date
from decimal import Decimal
from typing import List, Optional
from app.utils.decimal_utils import round_weight, round_percent, to_decimal
from app.domain.models import WeightLossSummary, BatchWeightLossItem

def calculate_weight_loss(
    start_date: date,
    end_date: date,
    purchases: List[any],
    sales: List[any],
    remaining_stock_kg: Decimal = Decimal("0.000"),
    returns_kg: Decimal = Decimal("0.000"),
    reconciled_loss_kg: Decimal = Decimal("0.000"),
    reconciled_gain_kg: Decimal = Decimal("0.000"),
    batch_details: Optional[List[BatchWeightLossItem]] = None
) -> WeightLossSummary:
    """
    Computes chicken stock weight loss for a date range taking into account
    inventory batches, remaining unsold stock, customer returns, and physical reconciliations.
    """
    total_purchased = Decimal("0.000")
    for pur in purchases:
        p_wt = getattr(pur, "net_weight_kg", None) or getattr(pur, "weight_kg", None) or Decimal("0.000")
        total_purchased += to_decimal(p_wt)

    total_gross = Decimal("0.000")
    total_box = Decimal("0.000")
    total_net = Decimal("0.000")

    for s in sales:
        total_gross += to_decimal(s.gross_weight_kg)
        total_box += to_decimal(s.box_weight_kg)
        total_net += to_decimal(s.net_weight_kg)

    purchased_kg = round_weight(total_purchased)
    sold_net_kg = round_weight(total_net)
    remaining_kg = round_weight(remaining_stock_kg)
    ret_kg = round_weight(returns_kg)
    rec_loss_kg = round_weight(reconciled_loss_kg)
    rec_gain_kg = round_weight(reconciled_gain_kg)
    details = batch_details or []

    if details:
        # True total weight loss is the sum of weight losses across batches
        weight_loss_kg = round_weight(sum((b.weight_loss_kg for b in details), Decimal("0.000")))
    elif remaining_kg > 0 or rec_loss_kg > 0 or ret_kg > 0:
        # Formula: Purchased - (Sold - Returns + Remaining)
        weight_loss_kg = round_weight(purchased_kg - (sold_net_kg - ret_kg + remaining_kg))
    else:
        weight_loss_kg = round_weight(purchased_kg - sold_net_kg)

    if purchased_kg > 0:
        loss_pct = round_percent((weight_loss_kg / purchased_kg) * Decimal("100"))
    else:
        loss_pct = Decimal("0.00")

    return WeightLossSummary(
        start_date=start_date,
        end_date=end_date,
        total_purchased_kg=purchased_kg,
        total_sales_gross_kg=round_weight(total_gross),
        total_sales_box_kg=round_weight(total_box),
        total_sales_net_kg=sold_net_kg,
        weight_loss_kg=weight_loss_kg,
        weight_loss_percentage=loss_pct,
        total_remaining_stock_kg=remaining_kg,
        total_returns_net_kg=ret_kg,
        total_reconciled_loss_kg=rec_loss_kg,
        total_reconciled_gain_kg=rec_gain_kg,
        batch_details=details
    )
