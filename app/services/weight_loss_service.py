from datetime import date
from sqlalchemy.orm import Session
from app.database.connection import get_session
from app.database.models import Purchase, Sale
from app.domain.weight_loss import calculate_weight_loss
from app.domain.models import WeightLossSummary

class WeightLossService:
    @staticmethod
    def get_weight_loss_summary(start_date: date, end_date: date) -> WeightLossSummary:
        session = get_session()
        try:
            purchases = (
                session.query(Purchase)
                .filter(
                    Purchase.is_deleted == False,
                    Purchase.transaction_date >= start_date,
                    Purchase.transaction_date <= end_date
                )
                .all()
            )
            sales = (
                session.query(Sale)
                .filter(
                    Sale.is_deleted == False,
                    Sale.transaction_date >= start_date,
                    Sale.transaction_date <= end_date
                )
                .all()
            )

            return calculate_weight_loss(
                start_date=start_date,
                end_date=end_date,
                purchases=purchases,
                sales=sales
            )
        finally:
            session.close()
