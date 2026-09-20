from decimal import Decimal
from datetime import date
from app.services.master_service import MasterService

def test_customer_creation_and_soft_delete(setup_in_memory_db):
    cust = MasterService.create_customer(
        name="Test Customer Delete",
        phone="1234567890",
        opening_balance=Decimal("100.00")
    )
    assert cust.id is not None
    
    customers = MasterService.get_all_customers()
    assert any(c.id == cust.id for c in customers)

    success = MasterService.soft_delete_customer(cust.id)
    assert success is True

    remaining = MasterService.get_all_customers()
    assert not any(c.id == cust.id for c in remaining)

def test_provider_creation_and_soft_delete(setup_in_memory_db):
    prov = MasterService.create_provider(
        name="Test Provider Delete",
        phone="0987654321",
        opening_balance=Decimal("200.00")
    )
    assert prov.id is not None

    providers = MasterService.get_all_providers()
    assert any(p.id == prov.id for p in providers)

    success = MasterService.soft_delete_provider(prov.id)
    assert success is True

    remaining = MasterService.get_all_providers()
    assert not any(p.id == prov.id for p in remaining)
