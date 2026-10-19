"""
Seed Data Script for Chicken Wholesale Shop Management System.
Deletes all current inputs in the database and starts fresh with rich dummy data:
- Master items (Broiler Chicken, Country Chicken, Layer Chicken)
- Realistic Providers (Suguna Farms, Venkateshwara Hatcheries, Godrej Agrovet)
- Realistic Customers (Al-Rehman Hotel, Star Biryani Center, Green Chillies Restaurant, Taj Caterers, City Fresh Chicken Stall)
- Purchases with boxes, gross, box wt, net wt, generating unique date-reflective batch names: (Provider-Date-A/B/C)
- Single and multi-batch sales with boxes, gross, box wt, net wt, and rates
- Customer payments (Cash and Bank)
- Physical daily stock reconciliations with natural weight shrinkage
- Customer returns with boxes, box weight, gross, and net
- Explicitly closed batch to test reopen-on-return prompt
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from app.config.settings import get_db_path
from app.database import connection
from app.database.connection import init_db, get_session
from app.database.models import Item
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService
from app.services.reconciliation_service import ReconciliationService
from app.services.inventory_service import InventoryService
from app.services.customer_return_service import CustomerReturnService
from app.services.customer_rate_adjustment_service import CustomerRateAdjustmentService

def reset_and_seed_data():
    print("=" * 60)
    print("STARTING FRESH DATABASE RESET & DUMMY DATA SEEDING")
    print("=" * 60)

    # 1. Dispose engine and delete existing database file
    db_file = get_db_path()
    print(f"Target Database File: {db_file}")

    if connection._engine:
        connection._engine.dispose()
        connection._engine = None
        connection._SessionLocal = None

    for ext in ["", "-wal", "-shm"]:
        p = Path(f"{db_file}{ext}")
        if p.exists():
            try:
                p.unlink()
                print(f"Deleted existing database artifact: {p.name}")
            except Exception as e:
                print(f"Warning: could not delete {p}: {e}")

    # 2. Re-initialize database schema
    init_db()
    print("Database tables and schema initialized successfully.")

    session = get_session()
    try:
        # 3. Master Items
        print("\n[1/7] Seeding Master Items...")
        session.query(Item).delete()
        broiler = Item(name="Broiler Chicken", code="BROILER", is_active=True)
        country = Item(name="Country Chicken", code="COUNTRY", is_active=True)
        layer = Item(name="Layer Chicken", code="LAYER", is_active=True)
        session.add_all([broiler, country, layer])
        session.commit()
        print(f"✓ Items created: {broiler.name}, {country.name}, {layer.name}")

        # 4. Providers
        print("\n[2/7] Seeding Providers...")
        prov_suguna = MasterService.create_provider(
            "Suguna Farms",
            phone="9842100001",
            address="Coimbatore Road, Tamil Nadu",
            opening_balance=0,
            opening_balance_date=date(2026, 10, 1)
        )
        prov_venk = MasterService.create_provider(
            "Venkateshwara Hatcheries",
            phone="9842100002",
            address="Pune Highway, Maharashtra",
            opening_balance=0,
            opening_balance_date=date(2026, 10, 1)
        )
        prov_godrej = MasterService.create_provider(
            "Godrej Agrovet",
            phone="9842100003",
            address="Bangalore Highway, Karnataka",
            opening_balance=0,
            opening_balance_date=date(2026, 10, 1)
        )
        print(f"✓ Providers created: {prov_suguna.name}, {prov_venk.name}, {prov_godrej.name}")

        # 5. Customers
        print("\n[3/7] Seeding Customers...")
        cust_rehman = MasterService.create_customer(
            "Al-Rehman Hotel",
            phone="9123450001",
            address="Market Road, Downtown",
            opening_balance=15000,
            opening_balance_date=date(2026, 10, 1)
        )
        cust_star = MasterService.create_customer(
            "Star Biryani Center",
            phone="9123450002",
            address="Railway Station Junction",
            opening_balance=8000,
            opening_balance_date=date(2026, 10, 1)
        )
        cust_green = MasterService.create_customer(
            "Green Chillies Restaurant",
            phone="9123450003",
            address="Bypass Cross Road",
            opening_balance=0,
            opening_balance_date=date(2026, 10, 1)
        )
        cust_taj = MasterService.create_customer(
            "Taj Caterers",
            phone="9123450004",
            address="MG Road, North Extension",
            opening_balance=5000,
            opening_balance_date=date(2026, 10, 1)
        )
        cust_city = MasterService.create_customer(
            "City Fresh Chicken Stall",
            phone="9123450005",
            address="Shop #12, Wholesale Meat Complex",
            opening_balance=0,
            opening_balance_date=date(2026, 10, 1)
        )
        print(f"✓ Customers created: {cust_rehman.name}, {cust_star.name}, {cust_green.name}, {cust_taj.name}, {cust_city.name}")

        # 6. Purchases with date-reflective batch naming
        print("\n[4/7] Seeding Purchases & Batches...")
        d_yesterday = date(2026, 10, 18)
        d_today = date(2026, 10, 19)

        # Purchase 1 (Yesterday): Suguna - 20 boxes, Gross 630 kg, Box 30 kg -> Net 600 kg @ ₹140
        pur1 = PurchaseService.create_purchase(
            transaction_date=d_yesterday,
            provider_id=prov_suguna.id,
            item_id=broiler.id,
            gross_weight_kg=630.000,
            box_weight_kg=30.000,
            box_count=20,
            rate_per_kg=140.00,
            payment_type="CASH",
            voucher_number="VCH-1001",
            notes="Morning batch arrival - Suguna Broiler"
        )
        batch1 = pur1.batch
        print(f"✓ Purchase 1: {batch1.batch_number} | Net: {batch1.net_weight_kg} KG from {prov_suguna.name}")

        # Purchase 2 (Yesterday): Venkateshwara - 15 boxes, Gross 422.5 kg, Box 22.5 kg -> Net 400 kg @ ₹142
        pur2 = PurchaseService.create_purchase(
            transaction_date=d_yesterday,
            provider_id=prov_venk.id,
            item_id=broiler.id,
            gross_weight_kg=422.500,
            box_weight_kg=22.500,
            box_count=15,
            rate_per_kg=142.00,
            payment_type="BANK",
            bank_reference="NEFT-VENK-9810",
            notes="Morning delivery - Venky Broiler"
        )
        batch2 = pur2.batch
        print(f"✓ Purchase 2: {batch2.batch_number} | Net: {batch2.net_weight_kg} KG from {prov_venk.name}")

        # Purchase 3 (Yesterday): Godrej - 10 boxes, Gross 215 kg, Box 15 kg -> Net 200 kg @ ₹220 (Country Chicken)
        pur3 = PurchaseService.create_purchase(
            transaction_date=d_yesterday,
            provider_id=prov_godrej.id,
            item_id=country.id,
            gross_weight_kg=215.000,
            box_weight_kg=15.000,
            box_count=10,
            rate_per_kg=220.00,
            payment_type="CASH",
            voucher_number="VCH-1002",
            notes="Premium Country Chicken Batch"
        )
        batch3 = pur3.batch
        print(f"✓ Purchase 3: {batch3.batch_number} | Net: {batch3.net_weight_kg} KG from {prov_godrej.name}")

        # Purchase 4 (Today): Suguna - 25 boxes, Gross 787.5 kg, Box 37.5 kg -> Net 750 kg @ ₹145
        pur4 = PurchaseService.create_purchase(
            transaction_date=d_today,
            provider_id=prov_suguna.id,
            item_id=broiler.id,
            gross_weight_kg=787.500,
            box_weight_kg=37.500,
            box_count=25,
            rate_per_kg=145.00,
            payment_type="CASH",
            voucher_number="VCH-1003",
            notes="Today Morning Fresh Stock"
        )
        batch4 = pur4.batch
        print(f"✓ Purchase 4: {batch4.batch_number} | Net: {batch4.net_weight_kg} KG from {prov_suguna.name}")

        # Purchase 5 (Today 2nd batch from same provider): Suguna - 10 boxes, Gross 315 kg, Box 15 kg -> Net 300 kg @ ₹145
        pur5 = PurchaseService.create_purchase(
            transaction_date=d_today,
            provider_id=prov_suguna.id,
            item_id=broiler.id,
            gross_weight_kg=315.000,
            box_weight_kg=15.000,
            box_count=10,
            rate_per_kg=145.00,
            payment_type="BANK",
            bank_reference="UPI-SUGUNA-2026",
            notes="Today Afternoon Supplementary Batch"
        )
        batch5 = pur5.batch
        print(f"✓ Purchase 5: {batch5.batch_number} | Net: {batch5.net_weight_kg} KG from {prov_suguna.name}")

        # 7. Sales Transactions
        print("\n[5/7] Seeding Sales & Multi-Batch Allocations...")

        # Sale 1 (Yesterday): Al-Rehman Hotel - 5 boxes, Gross 158 kg, Box 8 kg -> Net 150 kg @ ₹175
        sale1 = SalesService.create_sale(
            transaction_date=d_yesterday,
            customer_id=cust_rehman.id,
            item_id=broiler.id,
            gross_weight_kg=158.000,
            box_weight_kg=8.000,
            box_count=5,
            rate_per_kg=175.00,
            discount_amount=0.00,
            batch_id=batch1.id,
            notes="Morning delivery for biryani preparation"
        )
        print(f"✓ Sale 1: Sale #{sale1.id} to {cust_rehman.name} (150 KG from {batch1.batch_number})")

        # Sale 2 (Yesterday): Star Biryani Center - 6 boxes, Gross 189 kg, Box 9 kg -> Net 180 kg @ ₹178
        sale2 = SalesService.create_sale(
            transaction_date=d_yesterday,
            customer_id=cust_star.id,
            item_id=broiler.id,
            gross_weight_kg=189.000,
            box_weight_kg=9.000,
            box_count=6,
            rate_per_kg=178.00,
            discount_amount=200.00,
            batch_id=batch2.id,
            notes="Regular daily order"
        )
        print(f"✓ Sale 2: Sale #{sale2.id} to {cust_star.name} (180 KG from {batch2.batch_number})")

        # Sale 3 (Yesterday): Green Chillies Restaurant - 2 boxes, Gross 43 kg, Box 3 kg -> Net 40 kg @ ₹260 (Country Chicken)
        sale3 = SalesService.create_sale(
            transaction_date=d_yesterday,
            customer_id=cust_green.id,
            item_id=country.id,
            gross_weight_kg=43.000,
            box_weight_kg=3.000,
            box_count=2,
            rate_per_kg=260.00,
            discount_amount=0.00,
            batch_id=batch3.id,
            notes="Special Country Chicken consignment"
        )
        print(f"✓ Sale 3: Sale #{sale3.id} to {cust_green.name} (40 KG from {batch3.batch_number})")

        # Sale 4 (Today): MULTI-BATCH SALE! Taj Caterers - 8 boxes, Gross 262 kg, Box 12 kg -> Net 250 kg
        # 100 kg from batch1, 150 kg from batch2
        multi_allocs = [
            {
                "batch_id": batch1.id,
                "box_count": 3,
                "gross_weight_kg": Decimal("104.500"),
                "box_weight_kg": Decimal("4.500"),
                "net_weight_kg": Decimal("100.000"),
                "rate_per_kg": Decimal("180.00"),
                "amount": Decimal("18000.00")
            },
            {
                "batch_id": batch2.id,
                "box_count": 5,
                "gross_weight_kg": Decimal("157.500"),
                "box_weight_kg": Decimal("7.500"),
                "net_weight_kg": Decimal("150.000"),
                "rate_per_kg": Decimal("180.00"),
                "amount": Decimal("27000.00")
            }
        ]
        sale4 = SalesService.create_sale(
            transaction_date=d_today,
            customer_id=cust_taj.id,
            item_id=broiler.id,
            gross_weight_kg=262.000,
            box_weight_kg=12.000,
            box_count=8,
            rate_per_kg=180.00,
            discount_amount=500.00,
            allocations=multi_allocs,
            notes="Wedding catering order split across yesterday's remaining batches"
        )
        print(f"✓ Sale 4 (Multi-Batch): Sale #{sale4.id} to {cust_taj.name} (100 KG from {batch1.batch_number} + 150 KG from {batch2.batch_number})")

        # Sale 5 (Today): City Fresh Chicken Stall - 4 boxes, Gross 126 kg, Box 6 kg -> Net 120 kg @ ₹182
        sale5 = SalesService.create_sale(
            transaction_date=d_today,
            customer_id=cust_city.id,
            item_id=broiler.id,
            gross_weight_kg=126.000,
            box_weight_kg=6.000,
            box_count=4,
            rate_per_kg=182.00,
            discount_amount=0.00,
            batch_id=batch4.id,
            notes="Counter stock sale"
        )
        print(f"✓ Sale 5: Sale #{sale5.id} to {cust_city.name} (120 KG from {batch4.batch_number})")

        # 8. Customer Payments
        print("\n[6/7] Seeding Payments...")
        PaymentService.create_customer_payment(
            payment_date=d_yesterday,
            customer_id=cust_rehman.id,
            amount=25000.00,
            payment_mode="CASH",
            voucher_number="RCPT-501",
            notes="Advance cash settlement"
        )
        PaymentService.create_customer_payment(
            payment_date=d_today,
            customer_id=cust_star.id,
            amount=20000.00,
            payment_mode="BANK",
            bank_reference="UPI/SBI/88219",
            notes="Online transfer"
        )
        print("✓ Customer payments recorded.")

        # 9. Stock Reconciliations & Customer Returns
        print("\n[7/7] Seeding Daily Reconciliations, Closed Batch & Customer Returns...")

        # Physical reconciliation for Yesterday (2026-10-18):
        # Batch 1 (Suguna): Purchased 600 kg - Sold 150 kg = 450 kg calculated.
        # Actual weighed closing stock: 448.5 kg (-1.5 kg natural shrinkage / evaporation)
        ReconciliationService.reconcile_batch(
            batch_id=batch1.id,
            business_date=d_yesterday,
            actual_closing_stock=448.500,
            reason="Natural weight loss during storage & handling",
            notes="Evening physical weighing"
        )
        print(f"✓ Reconciled {batch1.batch_number} for {d_yesterday}: -1.500 KG shrinkage recorded.")

        # Batch 2 (Venky): Purchased 400 kg - Sold 180 kg = 220 kg calculated.
        # Actual weighed closing stock: 218.0 kg (-2.0 kg shrinkage)
        ReconciliationService.reconcile_batch(
            batch_id=batch2.id,
            business_date=d_yesterday,
            actual_closing_stock=218.000,
            reason="Water weight loss / cooling shrinkage",
            notes="Physical check verified"
        )
        print(f"✓ Reconciled {batch2.batch_number} for {d_yesterday}: -2.000 KG shrinkage recorded.")

        # Customer Return: Al-Rehman Hotel returns 1 box (Gross 21 kg, Box 1 kg -> Net 20 kg) on 2026-10-19 against Sale 1
        return_lines = [{
            "sale_batch_allocation_id": sale1.allocations[0].id,
            "batch_id": batch1.id,
            "box_count": 1,
            "returned_gross_weight_kg": Decimal("21.000"),
            "returned_box_weight_kg": Decimal("1.000"),
            "returned_net_weight_kg": Decimal("20.000"),
            "rate_per_kg": sale1.rate_per_kg,
            "financial_credit_amount": Decimal("3500.00"),
            "resale_eligible": True,
            "return_reason": "Excess Order / Customer Returned",
            "notes": "Unused fresh crates returned in good condition"
        }]
        cr1 = CustomerReturnService.create_customer_return(
            customer_id=cust_rehman.id,
            original_sale_id=sale1.id,
            return_date=d_today,
            lines_data=return_lines,
            notes="Customer returned extra boxes before noon"
        )
        print(f"✓ Customer Return #{cr1.return_number} recorded: 20 KG returned by {cust_rehman.name} (Credit: ₹{cr1.financial_credit_amount})")

        # Explicitly Close Batch 3 (Country Chicken)
        # 200 kg purchased - 40 kg sold = 160 kg.
        # Mark as completely finished / closed with notes:
        InventoryService.finish_batch(
            batch_id=batch3.id,
            business_date=d_yesterday,
            reason="Special consignment completed & cleared",
            notes="Remaining quantity allocated for local staff welfare & cleared"
        )
        print(f"✓ Closed Batch: {batch3.batch_number} marked as CLOSED.")
        print(f"  (Tip: Test reopening this batch by trying to record a return on Sale #{sale3.id}!)")

        print("\n" + "=" * 60)
        print("ALL DUMMY DATA SEEDED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        session.close()

if __name__ == "__main__":
    reset_and_seed_data()
