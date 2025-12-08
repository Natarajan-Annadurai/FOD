import pytest
from django.urls import reverse
from detection.models import ToolCreation, ToolPurchase, Inventory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------
# TEST: GET - Load Tool Creation Page
# ---------------------------------------------------------
def test_tool_creation_page_loads(client):
    url = reverse("tool_creation")
    response = client.get(url)

    assert response.status_code == 200
    assert b"Tool Creation" in response.content


# ---------------------------------------------------------
# TEST: Create New Tool
# ---------------------------------------------------------
def test_create_new_tool(client):
    url = reverse("tool_creation")

    response = client.post(
        url,
        {
            "tool_id": "TL-TEST-001",
            "tool_name": "Hammer",
            "description": "Heavy duty hammer",
            "part_number": "PN-55",
            "brand": "Bosch",
            "tool_type": "Maintenance",
            "remarks": "Test remark",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    tool = ToolCreation.objects.first()
    assert tool.tool_name == "Hammer"
    assert tool.tool_id == "TL-TEST-001"


# ---------------------------------------------------------
# TEST: Edit Existing Tool
# ---------------------------------------------------------
def test_edit_tool(client):
    tool = ToolCreation.objects.create(
        tool_id="TL-OLD-1",
        tool_name="Old Tool",
        description="old desc",
        part_number="123",
        brand="BrandA",
        tool_type="Cutting",
        remarks="Old",
    )

    url = reverse("tool_creation")

    response = client.post(
        url,
        {
            "internal_id": tool.id,
            "tool_id": "TL-NEW-1",
            "tool_name": "Updated Tool",
            "description": "Updated desc",
            "part_number": "999",
            "brand": "BrandB",
            "tool_type": "Measuring",
            "remarks": "Updated",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    tool.refresh_from_db()
    assert tool.tool_name == "Updated Tool"
    assert tool.brand == "BrandB"
    assert tool.part_number == "999"


# ---------------------------------------------------------
# TEST: Delete Tool
# ---------------------------------------------------------
def test_delete_tool(client):
    tool = ToolCreation.objects.create(
        tool_id="TL-DEL-1",
        tool_name="Delete Tool"
    )

    url = reverse("tool_delete", args=[tool.id])

    response = client.post(
        url, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert ToolCreation.objects.count() == 0


# ---------------------------------------------------------
# TEST: Tool Purchase + Inventory Update
# ---------------------------------------------------------
def test_tool_purchase_and_inventory_update(client):
    tool = ToolCreation.objects.create(
        tool_id="TL-PUR-1",
        tool_name="Tester Tool"
    )

    url = reverse("tool_purchase")

    response = client.post(
        url,
        {
            "tool_id": tool.id,
            "supplier_name": "SupplierA",
            "invoice_number": "INV-123",
            "quantity": 10,
            "unit_cost": 50,
            "purchase_cost": 500,
            "purchase_date": "2025-01-01",
            "calibration": "",
            "remarks": "",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check Purchase Record
    purchase = ToolPurchase.objects.first()
    assert purchase.tool == tool
    assert purchase.quantity == 10
    assert purchase.unit_cost == 50

    # Check Inventory
    inventory = Inventory.objects.get(tool=tool)
    assert inventory.total_quantity == 10
    assert inventory.in_stock == 10


# ---------------------------------------------------------
# TEST: Inventory increments on second purchase
# ---------------------------------------------------------
def test_inventory_increment_on_second_purchase(client):
    tool = ToolCreation.objects.create(
        tool_id="TL-ADD-1",
        tool_name="Addition Tool"
    )

    Inventory.objects.create(tool=tool, total_quantity=5, assigned_quantity=0)

    url = reverse("tool_purchase")

    client.post(
        url,
        {
            "tool_id": tool.id,
            "supplier_name": "VendorX",
            "invoice_number": "INV-2",
            "quantity": 7,
            "unit_cost": 20,
            "purchase_cost": 140,
            "purchase_date": "2025-01-02"
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    inv = Inventory.objects.get(tool=tool)

    assert inv.total_quantity == 12
    assert inv.in_stock == 12