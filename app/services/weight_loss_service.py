from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session
from app.database.models import (
    Purchase, Sale, PurchaseBatch, InventoryMovement, CustomerReturn, CustomerReturnLine
)
from app.domain.weight_loss import calculate_weight_loss
from app.domain.models import WeightLossSummary, BatchWeightLossItem
from app.utils.decimal_utils import round_weight, round_percent, to_decimal

class WeightLossService:
    @staticmethod
    def get_weight_loss_summary(start_date: date, end_date: date) -> WeightLossSummary:
        """
        Computes comprehensive weight loss analysis taking into account:
        - Intake weight per batch (purchases)
        - Sold net weight per batch
        - Restocked customer returns per batch
        - Remaining unsold stock currently in batches
        - Physical stock count discrepancies (shrinkage & gains) from daily reconciliation
        - Final zeroing adjustments upon batch completion
        """
        session = get_session()
        try:
            # 1. Purchases in period
            purchases = (
                session.query(Purchase)
                .filter(
                    Purchase.is_deleted == False,
                    Purchase.transaction_date >= start_date,
                    Purchase.transaction_date <= end_date
                )
                .all()
            )

            # 2. Sales in period
            sales = (
                session.query(Sale)
                .filter(
                    Sale.is_deleted == False,
                    Sale.transaction_date >= start_date,
                    Sale.transaction_date <= end_date
                )
                .all()
            )

            # 3. Customer Returns in period
            return_lines = (
                session.query(CustomerReturnLine)
                .join(CustomerReturn, CustomerReturnLine.customer_return_id == CustomerReturn.id)
                .filter(
                    CustomerReturn.is_deleted == False,
                    CustomerReturn.return_date >= start_date,
                    CustomerReturn.return_date <= end_date
                )
                .all()
            )
            total_returns_kg = sum((to_decimal(r.returned_net_weight_kg) for r in return_lines), Decimal("0.000"))

            # 4. Fetch relevant batches
            # Batches purchased in [start_date, end_date], or active batches with stock, or batches with movements in period
            movement_batch_ids = [
                r[0] for r in session.query(InventoryMovement.batch_id)
                .filter(
                    InventoryMovement.business_date >= start_date,
                    InventoryMovement.business_date <= end_date
                )
                .distinct()
                .all()
            ]

            batches = (
                session.query(PurchaseBatch)
                .options(
                    joinedload(PurchaseBatch.item),
                    joinedload(PurchaseBatch.purchase).joinedload(Purchase.provider),
                    joinedload(PurchaseBatch.movements)
                )
                .filter(
                    PurchaseBatch.is_deleted == False,
                    (
                        (PurchaseBatch.purchase_date >= start_date) & (PurchaseBatch.purchase_date <= end_date)
                    ) | (
                        PurchaseBatch.id.in_(movement_batch_ids) if movement_batch_ids else False
                    ) | (
                        (PurchaseBatch.purchase_date <= end_date) & (PurchaseBatch.status != "CLOSED")
                    )
                )
                .order_by(PurchaseBatch.purchase_date.desc(), PurchaseBatch.id.desc())
                .all()
            )

            batch_details: List[BatchWeightLossItem] = []
            total_remaining_stock = Decimal("0.000")
            total_recon_loss = Decimal("0.000")
            total_recon_gain = Decimal("0.000")

            for b in batches:
                intake_net = round_weight(b.net_weight_kg)
                remaining_stock = round_weight(b.current_stock_kg)

                # Analyze movements for this batch
                movements = b.movements or []
                sold_net = Decimal("0.000")
                ret_net = Decimal("0.000")
                recon_loss = Decimal("0.000")
                recon_gain = Decimal("0.000")

                for m in movements:
                    if m.movement_type == "SALE":
                        sold_net += abs(to_decimal(m.quantity_kg))
                    elif m.movement_type == "CUSTOMER_RETURN":
                        ret_net += to_decimal(m.quantity_kg)
                    elif m.movement_type in ("STOCK_LOSS", "STOCK_ADJUSTMENT") and m.quantity_kg < 0:
                        recon_loss += abs(to_decimal(m.quantity_kg))
                    elif m.movement_type in ("STOCK_GAIN", "STOCK_ADJUSTMENT") and m.quantity_kg > 0:
                        recon_gain += to_decimal(m.quantity_kg)

                sold_net = round_weight(sold_net)
                ret_net = round_weight(ret_net)
                recon_loss = round_weight(recon_loss)
                recon_gain = round_weight(recon_gain)

                # True weight loss: Intake - (Sold - Returns + Remaining Stock)
                # Unsold chicken still in stock is NOT lost.
                batch_loss = round_weight(intake_net - (sold_net - ret_net + remaining_stock))
                batch_loss_pct = round_percent((batch_loss / intake_net) * Decimal("100")) if intake_net > 0 else Decimal("0.00")

                prov_name = (
                    b.purchase.provider.name if (b.purchase and b.purchase.provider) else "Direct"
                )
                itm_name = b.item.name if b.item else "Chicken"

                item_obj = BatchWeightLossItem(
                    batch_id=b.id,
                    batch_number=b.batch_number,
                    purchase_date=b.purchase_date,
                    item_name=itm_name,
                    provider_name=prov_name,
                    intake_net_kg=intake_net,
                    sold_net_kg=sold_net,
                    returned_net_kg=ret_net,
                    remaining_stock_kg=remaining_stock,
                    reconciled_loss_kg=recon_loss,
                    reconciled_gain_kg=recon_gain,
                    weight_loss_kg=batch_loss,
                    weight_loss_percentage=batch_loss_pct,
                    status=b.status,
                    notes=b.closed_notes
                )
                batch_details.append(item_obj)

                total_remaining_stock += remaining_stock
                total_recon_loss += recon_loss
                total_recon_gain += recon_gain

            return calculate_weight_loss(
                start_date=start_date,
                end_date=end_date,
                purchases=purchases,
                sales=sales,
                remaining_stock_kg=round_weight(total_remaining_stock),
                returns_kg=round_weight(total_returns_kg),
                reconciled_loss_kg=round_weight(total_recon_loss),
                reconciled_gain_kg=round_weight(total_recon_gain),
                batch_details=batch_details
            )
        finally:
            session.close()
