from datetime import date
from decimal import Decimal
from typing import List
from app.utils.decimal_utils import round_weight, round_percent, to_decimal
from app.domain.models import WeightLossSummary

def calculate_weight_loss(
    start_date: date,
    end_date: date,
    purchases: List[any],
    sales: List[any]
) -> WeightLossSummary:
    """
    Computes chicken stock weight loss for a date range.
    Uses Purchase Weight vs Sales Net Weight.
    """
    total_purchased = Decimal("0.000")
    for pur in purchases:
        total_purchased += to_decimal(pur.weight_kg)

    total_gross = Decimal("0.000")
    total_box = Decimal("0.000")
    total_net = Decimal("0.000")

    for s in sales:
        total_gross += to_decimal(s.gross_weight_kg)
        total_box += to_decimal(s.box_weight_kg)
        total_net += to_decimal(s.net_weight_kg)

    purchased_kg = round_weight(total_purchased)
    sold_net_kg = round_weight(total_net)

    weight_loss_kg = purchased_kg - sold_net_kg
    
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
        weight_loss_percentage=loss_pct
    )
