"""
Seed Data Script for Chicken Wholesale Shop Management System.
Populates realistic providers, customers, items, purchases, sales, and payments.
"""

from datetime import date
from app.database.connection import init_db
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService

def seed_sample_data():
    init_db()
    print("Initializing Database Seed...")

    # 1. Chicken Types (Master)
    items = MasterService.get_all_items()
    broiler = items[0]  # Broiler
    country = items[1] if len(items) > 1 else items[0]

    # 2. Providers
    prov_a = MasterService.create_provider("Provider A", phone="9876543210", opening_balance=0, opening_balance_date=date(2026, 9, 1))
    prov_b = MasterService.create_provider("Provider B", phone="9876543211", opening_balance=0, opening_balance_date=date(2026, 9, 1))
    prov_c = MasterService.create_provider("Provider C", phone="9876543212", opening_balance=0, opening_balance_date=date(2026, 9, 1))

    # 3. Customers
    cust_abc = MasterService.create_customer("ABC Hotel", phone="9123456780", address="123 Main Road", opening_balance=50000, opening_balance_date=date(2026, 9, 1))
    cust_xyz = MasterService.create_customer("Hotel XYZ", phone="9123456781", address="45 Station Ave", opening_balance=25000, opening_balance_date=date(2026, 9, 1))
    cust_res = MasterService.create_customer("Restaurant ABC", phone="9123456782", address="78 Highway St", opening_balance=0, opening_balance_date=date(2026, 9, 1))

    # 4. Purchases (Shop buying chicken from providers)
    # 20/09/2026: Provider A, 500 KG @ ₹150 = ₹75,000 Cash (Voucher P-501)
    PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=prov_a.id,
        item_id=broiler.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="CASH",
        voucher_number="P-501"
    )

    # 20/09/2026: Provider B, 300 KG @ ₹150 = ₹45,000 Bank
    PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=prov_b.id,
        item_id=broiler.id,
        weight_kg=300,
        rate_per_kg=150,
        payment_type="BANK",
        bank_reference="NEFT2001"
    )

    # 20/09/2026: Provider C, 200 KG @ ₹155 = ₹31,000 Cash (Voucher P-502)
    PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=prov_c.id,
        item_id=country.id,
        weight_kg=200,
        rate_per_kg=155,
        payment_type="CASH",
        voucher_number="P-502"
    )

    # 5. Sales (Shop selling chicken to customers)
    # Day 1: ABC Hotel - Gross=100, Box=5 -> Net=95 KG @ ₹180 = ₹17,100
    SalesService.create_sale(
        transaction_date=date(2026, 9, 2),
        customer_id=cust_abc.id,
        item_id=broiler.id,
        gross_weight_kg=100,
        box_weight_kg=5,
        rate_per_kg=180
    )

    # Day 2: ABC Hotel pays Cash ₹20,000 (Voucher C-1025)
    PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 3),
        customer_id=cust_abc.id,
        amount=20000,
        payment_mode="CASH",
        voucher_number="C-1025"
    )

    # Day 3: ABC Hotel - Gross=200, Box=10 -> Net=190 KG @ ₹185 = ₹35,150
    SalesService.create_sale(
        transaction_date=date(2026, 9, 5),
        customer_id=cust_abc.id,
        item_id=broiler.id,
        gross_weight_kg=200,
        box_weight_kg=10,
        rate_per_kg=185
    )

    # Hotel XYZ Sale: Gross=150, Box=8 -> Net=142 KG @ ₹190 = ₹26,980
    SalesService.create_sale(
        transaction_date=date(2026, 9, 10),
        customer_id=cust_xyz.id,
        item_id=broiler.id,
        gross_weight_kg=150,
        box_weight_kg=8,
        rate_per_kg=190
    )

    # Hotel XYZ Bank payment ₹15,000
    PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 12),
        customer_id=cust_xyz.id,
        amount=15000,
        payment_mode="BANK",
        bank_reference="UPI/98765"
    )

    print("Sample Data Seeding Complete!")

if __name__ == "__main__":
    seed_sample_data()
