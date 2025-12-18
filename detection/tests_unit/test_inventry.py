import pytest
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from inventory.models import Inventory, Tool
from detection.models import ToolEventTracking

pytestmark = pytest.mark.django_db

@pytest.fixture
def client(client):
    user = User.objects.create_user(username="testuser", password="pass123")
    client.login(username="testuser", password="pass123")
    return client
@pytest.fixture
def tool():
    return Tool.objects.create(
        tool_id="TL-001",
        tool_name="Torque Wrench"
    )

@pytest.fixture
def inventory(tool):
    return Inventory.objects.create(
        inventory_id="INV-001",
        tool=tool,
        total_quantity=5,
        in_stock=5,
        assigned_quantity=0,
        available_quantity=5,
        in_use=0,
        damaged=0
    )

def test_update_inventory_tool_issued(inventory):
    event = ToolEventTracking.objects.create(
        tool_id=inventory.tool.tool_id,
        event="tool_Issued",
        timestamp=timezone.now()
    )

    from inventory.views import update_inventory_for_event
    result = update_inventory_for_event(event)

    inventory.refresh_from_db()

    assert result["success"] is True
    assert inventory.available_quantity == 4
    assert inventory.in_use == 1

def test_update_inventory_tool_returned(inventory):
    inventory.in_use = 2
    inventory.available_quantity = 3
    inventory.save()

    event = ToolEventTracking.objects.create(
        tool_id=inventory.tool.tool_id,
        event="tool_Returned",
        timestamp=timezone.now()
    )

    from inventory.views import update_inventory_for_event
    result = update_inventory_for_event(event)

    inventory.refresh_from_db()

    assert result["success"] is True
    assert inventory.available_quantity == 4
    assert inventory.in_use == 1

def test_update_inventory_tool_returned(inventory):
    inventory.in_use = 2
    inventory.available_quantity = 3
    inventory.save()

    event = ToolEventTracking.objects.create(
        tool_id=inventory.tool.tool_id,
        event="tool_Returned",
        timestamp=timezone.now()
    )

    from inventory.views import update_inventory_for_event
    result = update_inventory_for_event(event)

    inventory.refresh_from_db()

    assert result["success"] is True
    assert inventory.available_quantity == 4
    assert inventory.in_use == 1

def test_update_inventory_tool_not_found():
    event = ToolEventTracking.objects.create(
        tool_id="INVALID",
        event="tool_Issued",
        timestamp=timezone.now()
    )

    from inventory.views import update_inventory_for_event
    result = update_inventory_for_event(event)

    assert result["success"] is False
    assert result["error"] == "Tool not found in inventory"

def test_update_inventory_no_update_possible(inventory):
    inventory.available_quantity = 0
    inventory.save()

    event = ToolEventTracking.objects.create(
        tool_id=inventory.tool.tool_id,
        event="tool_Issued",
        timestamp=timezone.now()
    )

    from inventory.views import update_inventory_for_event
    result = update_inventory_for_event(event)

    assert result["success"] is False
    assert result["error"] == "No inventory update possible"

def test_inventory_update_api_success(client, inventory):
    ToolEventTracking.objects.create(
        tool_id=inventory.tool.tool_id,
        event="tool_Issued",
        timestamp=timezone.now()
    )

    url = reverse("inventory_update_api")
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["event"] == "tool_Issued"
    assert data["available_quantity"] == 4
    assert data["in_use"] == 1

def test_inventory_update_api_no_event(client):
    url = reverse("inventory_update_api")
    response = client.get(url)

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"] == "No recent event found"


