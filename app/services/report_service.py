from datetime import date
from decimal import Decimal
from typing import Dict, List, Any
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_session
from app.database.models import Purchase, Sale, CustomerPayment, ProviderPayment
from app.utils.decimal_utils import round_money, round_weight, to_decimal

class ReportService:
    @staticmethod
    def get_purchase_summary(
        start_date: date,
        end_date: date,
        provider_id: int | None = None,
        item_id: int | None = None
    ) -> Dict[str, Any]:
        session = get_session()
        try:
            query = (
                session.query(Purchase)
                .options(joinedload(Purchase.provider), joinedload(Purchase.item))
                .filter(
                    Purchase.is_deleted == False,
                    Purchase.transaction_date >= start_date,
                    Purchase.transaction_date <= end_date
                )
            )
            if provider_id:
                query = query.filter(Purchase.provider_id == provider_id)
            if item_id:
                query = query.filter(Purchase.item_id == item_id)

            purchases = query.all()

            total_weight = Decimal("0.000")
            total_amount = Decimal("0.00")
            cash_amount = Decimal("0.00")
            bank_amount = Decimal("0.00")
            providers_set = set()

            provider_breakdown = {}

            for p in purchases:
                wt = to_decimal(p.weight_kg)
                amt = to_decimal(p.total_amount)
                total_weight += wt
                total_amount += amt
                providers_set.add(p.provider_id)

                if p.payment_type == "CASH":
                    cash_amount += amt
                else:
                    bank_amount += amt

                p_name = p.provider.name if p.provider else "Unknown Provider"
                if p_name not in provider_breakdown:
                    provider_breakdown[p_name] = {
                        "weight_kg": Decimal("0.000"),
                        "amount": Decimal("0.00"),
                        "cash": Decimal("0.00"),
                        "bank": Decimal("0.00")
                    }
                provider_breakdown[p_name]["weight_kg"] += wt
                provider_breakdown[p_name]["amount"] += amt
                if p.payment_type == "CASH":
                    provider_breakdown[p_name]["cash"] += amt
                else:
                    provider_breakdown[p_name]["bank"] += amt

            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_weight_kg": round_weight(total_weight),
                "total_amount": round_money(total_amount),
                "cash_amount": round_money(cash_amount),
                "bank_amount": round_money(bank_amount),
                "provider_count": len(providers_set),
                "provider_breakdown": provider_breakdown,
                "records": purchases
            }
        finally:
            session.close()

    @staticmethod
    def get_sales_summary(
        start_date: date,
        end_date: date,
        customer_id: int | None = None,
        item_id: int | None = None
    ) -> Dict[str, Any]:
        session = get_session()
        try:
            query = (
                session.query(Sale)
                .options(joinedload(Sale.customer), joinedload(Sale.item))
                .filter(
                    Sale.is_deleted == False,
                    Sale.transaction_date >= start_date,
                    Sale.transaction_date <= end_date
                )
            )
            if customer_id:
                query = query.filter(Sale.customer_id == customer_id)
            if item_id:
                query = query.filter(Sale.item_id == item_id)

            sales = query.all()

            total_gross = Decimal("0.000")
            total_box = Decimal("0.000")
            total_net = Decimal("0.000")
            total_discount = Decimal("0.00")
            total_amount = Decimal("0.00")
            total_boxes = 0
            customers_set = set()

            customer_breakdown = {}

            for s in sales:
                gross = to_decimal(s.gross_weight_kg)
                box = to_decimal(s.box_weight_kg)
                net = to_decimal(s.net_weight_kg)
                disc = to_decimal(getattr(s, "discount_amount", 0.00))
                amt = to_decimal(s.total_amount)
                box_cnt = int(getattr(s, "box_count", 0) or 0)

                total_gross += gross
                total_box += box
                total_net += net
                total_discount += disc
                total_amount += amt
                total_boxes += box_cnt
                customers_set.add(s.customer_id)

                c_name = s.customer.name if s.customer else "Unknown Customer"
                if c_name not in customer_breakdown:
                    customer_breakdown[c_name] = {
                        "boxes": 0,
                        "gross_weight_kg": Decimal("0.000"),
                        "box_weight_kg": Decimal("0.000"),
                        "net_weight_kg": Decimal("0.000"),
                        "discount": Decimal("0.00"),
                        "amount": Decimal("0.00")
                    }
                customer_breakdown[c_name]["boxes"] += box_cnt
                customer_breakdown[c_name]["gross_weight_kg"] += gross
                customer_breakdown[c_name]["box_weight_kg"] += box
                customer_breakdown[c_name]["net_weight_kg"] += net
                customer_breakdown[c_name]["discount"] += disc
                customer_breakdown[c_name]["amount"] += amt

            avg_box_wt = round_weight(total_net / total_boxes) if total_boxes > 0 else Decimal("0.000")

            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_boxes_count": total_boxes,
                "avg_weight_per_box_kg": avg_box_wt,
                "total_gross_weight_kg": round_weight(total_gross),
                "total_box_weight_kg": round_weight(total_box),
                "total_net_weight_kg": round_weight(total_net),
                "total_discount_amount": round_money(total_discount),
                "total_amount": round_money(total_amount),
                "customer_count": len(customers_set),
                "customer_breakdown": customer_breakdown,
                "records": sales
            }
        finally:
            session.close()

    @staticmethod
    def get_payment_summary(start_date: date, end_date: date) -> Dict[str, Any]:
        session = get_session()
        try:
            cust_payments = (
                session.query(CustomerPayment)
                .options(joinedload(CustomerPayment.customer))
                .filter(
                    CustomerPayment.is_deleted == False,
                    CustomerPayment.payment_date >= start_date,
                    CustomerPayment.payment_date <= end_date
                )
                .all()
            )
            prov_payments = (
                session.query(ProviderPayment)
                .options(joinedload(ProviderPayment.provider))
                .filter(
                    ProviderPayment.is_deleted == False,
                    ProviderPayment.payment_date >= start_date,
                    ProviderPayment.payment_date <= end_date
                )
                .all()
            )

            cust_cash = sum((to_decimal(p.amount) for p in cust_payments if p.payment_mode == "CASH"), Decimal("0.00"))
            cust_bank = sum((to_decimal(p.amount) for p in cust_payments if p.payment_mode == "BANK"), Decimal("0.00"))

            prov_cash = sum((to_decimal(p.amount) for p in prov_payments if p.payment_mode == "CASH"), Decimal("0.00"))
            prov_bank = sum((to_decimal(p.amount) for p in prov_payments if p.payment_mode == "BANK"), Decimal("0.00"))

            return {
                "start_date": start_date,
                "end_date": end_date,
                "customer_cash": round_money(cust_cash),
                "customer_bank": round_money(cust_bank),
                "customer_total": round_money(cust_cash + cust_bank),
                "provider_cash": round_money(prov_cash),
                "provider_bank": round_money(prov_bank),
                "provider_total": round_money(prov_cash + prov_bank),
                "customer_payments": cust_payments,
                "provider_payments": prov_payments
            }
        finally:
            session.close()
