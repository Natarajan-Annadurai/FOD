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

def test_assigned_tools_list_get(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    url = reverse("assigned_tools_list", args=[tray.id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"All Assigned Tools" in response.content

def test_assigned_tool_displayed(client):
    user = User.objects.get(username="testuser")

    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool = Tool.objects.create(
        tool_id="TL-001",
        tool_name="Torque Wrench"
    )

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
        remarks="For maintenance"
    )

    url = reverse("assigned_tools_list", args=[tray.id])
    response = client.get(url)

    assert b"Torque Wrench" in response.content
    assert b"TL-001" in response.content
    assert b"3" in response.content
    assert user.username.encode() in response.content

def test_assigned_tools_quantity_filter(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    tool1 = Tool.objects.create(tool_id="TL-002", tool_name="Hammer")
    tool2 = Tool.objects.create(tool_id="TL-003", tool_name="Drill")

    inventory1 = Inventory.objects.create(
        inventory_id="INV-002",
        tool=tool1,
        in_stock=5,
        assigned_quantity=0,
        available_quantity=0
    )

    inventory2 = Inventory.objects.create(
        inventory_id="INV-003",
        tool=tool2,
        in_stock=5,
        assigned_quantity=2,
        available_quantity=2
    )

    TrayTool.objects.create(
        tray=tray,
        inventory=inventory1,
        tool_id=tool1.tool_id,
        assigned_quantity=0
    )

    TrayTool.objects.create(
        tray=tray,
        inventory=inventory2,
        tool_id=tool2.tool_id,
        assigned_quantity=2
    )

    url = reverse("assigned_tools_list", args=[tray.id])
    response = client.get(url)

    assert b"Drill" in response.content
    assert b"Hammer" not in response.content

def test_assigned_tools_empty(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)
    tray = Tray.objects.create(tray_name="Tray A", unit=unit)

    url = reverse("assigned_tools_list", args=[tray.id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"No tools assigned" in response.content

def test_assigned_tools_tray_specific(client):
    station = ServiceStation.objects.create(name="Station A")
    unit = Unit.objects.create(name="Unit A", station=station)

    tray1 = Tray.objects.create(tray_name="Tray A", unit=unit)
    tray2 = Tray.objects.create(tray_name="Tray B", unit=unit)

    tool = Tool.objects.create(tool_id="TL-004", tool_name="Screwdriver")

    inventory = Inventory.objects.create(
        inventory_id="INV-004",
        tool=tool,
        in_stock=10,
        assigned_quantity=2,
        available_quantity=2
    )

    TrayTool.objects.create(
        tray=tray1,
        inventory=inventory,
        tool_id=tool.tool_id,
        assigned_quantity=2
    )

    url = reverse("assigned_tools_list", args=[tray2.id])
    response = client.get(url)

    assert b"Screwdriver" not in response.content

