import pytest
from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.payment_service import PaymentService

def test_customer_and_provider_payments_and_voucher_rules():
    cust = MasterService.create_customer(name="Customer Payment Test")
    prov = MasterService.create_provider(name="Provider Payment Test")

    # Customer Cash Payment requires voucher
    cp1 = PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 20),
        customer_id=cust.id,
        amount=5000,
        payment_mode="CASH",
        voucher_number="RC-101"
    )
    assert cp1.amount == Decimal("5000.00")
    assert cp1.voucher_number == "RC-101"

    # Reject Customer Cash payment without voucher
    with pytest.raises(ValueError, match="Voucher number is required for CASH"):
        PaymentService.create_customer_payment(
            payment_date=date(2026, 9, 20),
            customer_id=cust.id,
            amount=2000,
            payment_mode="CASH"
        )

    # Provider Bank Payment without voucher
    pp1 = PaymentService.create_provider_payment(
        payment_date=date(2026, 9, 20),
        provider_id=prov.id,
        amount=10000,
        payment_mode="BANK",
        bank_reference="UPI/998877"
    )
    assert pp1.amount == Decimal("10000.00")
    assert pp1.bank_reference == "UPI/998877"

    # Global voucher search
    cust_res, prov_res = PaymentService.search_voucher("RC-101")
    assert len(cust_res) == 1
    assert cust_res[0].id == cp1.id
