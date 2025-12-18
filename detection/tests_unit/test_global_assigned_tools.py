import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client

from centralized.models import (
    ServiceStation,
    Unit,
    Tray,
    Tool,
    Inventory,
    TrayTool
)

pytestmark = pytest.mark.django_db

@pytest.fixture
def client():
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client

def test_global_assigned_tools_page_load(client):
    url = reverse("global_assigned_tools")
    response = client.get(url)

    assert response.status_code == 200
    assert b"All Assigned Tools" in response.content
    assert b"Filter Assignments" in response.content

def test_global_assigned_tools_data_display(client):
    user = User.objects.get(username="testuser")

    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool = Tool.objects.create(tool_id="TL-001", tool_name="Torque Wrench")

    inventory = Inventory.objects.create(
        inventory_id="INV-001",
        tool=tool,
        in_stock=5,
        assigned_quantity=3,
        available_quantity=3
    )

    TrayTool.objects.create(
        tray=tray,
        inventory=inventory,
        tool_id=tool.tool_id,
        assigned_quantity=3,
        assigned_by=user,
        remarks="Maintenance"
    )

    url = reverse("global_assigned_tools")
    response = client.get(url)

    assert b"Station A" in response.content
    assert b"Unit A" in response.content
    assert b"Tray A" in response.content
    assert b"TL-001" in response.content
    assert b"Torque Wrench" in response.content
    assert b"3" in response.content
    assert user.username.encode() in response.content

def test_global_assigned_tools_quantity_filter(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool1 = Tool.objects.create(tool_id="TL-002", tool_name="Hammer")
    tool2 = Tool.objects.create(tool_id="TL-003", tool_name="Drill")

    inv1 = Inventory.objects.create(
        inventory_id="INV-002",
        tool=tool1,
        in_stock=5,
        assigned_quantity=0,
        available_quantity=0
    )

    inv2 = Inventory.objects.create(
        inventory_id="INV-003",
        tool=tool2,
        in_stock=5,
        assigned_quantity=2,
        available_quantity=2
    )

    TrayTool.objects.create(
        tray=tray,
        inventory=inv1,
        tool_id=tool1.tool_id,
        assigned_quantity=0
    )

    TrayTool.objects.create(
        tray=tray,
        inventory=inv2,
        tool_id=tool2.tool_id,
        assigned_quantity=2
    )

    response = client.get(reverse("global_assigned_tools"))

    assert b"Drill" in response.content
    assert b"Hammer" not in response.content

def test_global_assigned_tools_filter_station(client):
    station1 = ServiceStation.objects.create(name="Station A")
    station2 = ServiceStation.objects.create(name="Station B")

    unit1 = Unit.objects.create(name="Unit A", station=station1)
    unit2 = Unit.objects.create(name="Unit B", station=station2)

    tray1 = Tray.objects.create(tray_name="Tray A", unit=unit1)
    tray2 = Tray.objects.create(tray_name="Tray B", unit=unit2)

    tool = Tool.objects.create(tool_id="TL-010", tool_name="Tester")

    inv = Inventory.objects.create(
        inventory_id="INV-010",
        tool=tool,
        in_stock=10,
        assigned_quantity=1,
        available_quantity=1
    )

    TrayTool.objects.create(tray=tray1, inventory=inv, tool_id=tool.tool_id, assigned_quantity=1)

    response = client.get(
        reverse("global_assigned_tools"),
        {"station_id": station2.id}
    )

    assert b"Tester" not in response.content

def test_global_assigned_tools_filter_unit_and_tray(client):
    station = ServiceStation.objects.create(name="Station A")
    unit1 = Unit.objects.create(name="Unit A", station=station)
    unit2 = Unit.objects.create(name="Unit B", station=station)

    tray1 = Tray.objects.create(tray_name="Tray A", unit=unit1)
    tray2 = Tray.objects.create(tray_name="Tray B", unit=unit2)

    tool = Tool.objects.create(tool_id="TL-020", tool_name="Spanner")

    inv = Inventory.objects.create(
        inventory_id="INV-020",
        tool=tool,
        in_stock=5,
        assigned_quantity=2,
        available_quantity=2
    )

    TrayTool.objects.create(tray=tray1, inventory=inv, tool_id=tool.tool_id, assigned_quantity=2)

    response = client.get(
        reverse("global_assigned_tools"),
        {"unit_id": unit2.id, "tray_id": tray2.id}
    )

    assert b"Spanner" not in response.content

def test_global_assigned_tools_filter_tool_id(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool = Tool.objects.create(tool_id="TL-ABC", tool_name="Caliper")

    inv = Inventory.objects.create(
        inventory_id="INV-ABC",
        tool=tool,
        in_stock=3,
        assigned_quantity=1,
        available_quantity=1
    )

    TrayTool.objects.create(tray=tray, inventory=inv, tool_id=tool.tool_id, assigned_quantity=1)

    response = client.get(
        reverse("global_assigned_tools"),
        {"tool_id": "ABC"}
    )

    assert b"Caliper" in response.content

def test_global_assigned_tools_filter_tool_name(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool = Tool.objects.create(tool_id="TL-XYZ", tool_name="Digital Multimeter")

    inv = Inventory.objects.create(
        inventory_id="INV-XYZ",
        tool=tool,
        in_stock=4,
        assigned_quantity=2,
        available_quantity=2
    )

    TrayTool.objects.create(tray=tray, inventory=inv, tool_id=tool.tool_id, assigned_quantity=2)

    response = client.get(
        reverse("global_assigned_tools"),
        {"tool_name": "Multimeter"}
    )

    assert b"Digital Multimeter" in response.content

def test_global_assigned_tools_empty_state(client):
    response = client.get(reverse("global_assigned_tools"))

    assert response.status_code == 200
    assert b"No tools assigned" in response.content
    assert b"No tool assignments match your current filters" in response.content

