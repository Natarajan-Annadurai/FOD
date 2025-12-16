import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client

from detection.models import (
    ServiceStation,
    Unit,
    Tray,
    TrayTool,
    JobToolUsage
)

pytestmark = pytest.mark.django_db


# -----------------------------
# Authenticated client
# -----------------------------
@pytest.fixture
def client():
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client


# -----------------------------
# Common fixtures
# -----------------------------
@pytest.fixture
def station():
    return ServiceStation.objects.create(name="Station A")


@pytest.fixture
def unit(station):
    return Unit.objects.create(
        station=station,
        name="Unit A"
    )


# -----------------------------
# Test: GET Tray Page
# -----------------------------
def test_create_tray_page_get(client, unit):
    url = reverse("create_tray", args=[unit.id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"Add Tray to Unit" in response.content


# -----------------------------
# Test: Create Tray Success
# -----------------------------
def test_create_tray_success(client, unit):
    url = reverse("create_tray", args=[unit.id])

    data = {
        "tray_name": "Tray A",
        "max_capacity": 10,
        "remarks": "Main tray"
    }

    response = client.post(url, data)

    assert response.status_code == 302
    tray = Tray.objects.get(tray_name="Tray A")

    assert tray.unit == unit
    assert tray.max_capacity == 10
    assert tray.remarks == "Main tray"


# -----------------------------
# Test: Create Tray via AJAX
# -----------------------------
def test_create_tray_ajax_success(client, unit):
    url = reverse("create_tray", args=[unit.id])

    data = {
        "tray_name": "Tray AJAX",
        "max_capacity": 5,
        "remarks": "Ajax tray"
    }

    response = client.post(
        url,
        data,
        HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert Tray.objects.filter(tray_name="Tray AJAX").exists()


# -----------------------------
# Test: Edit Tray Success
# -----------------------------
def test_edit_tray_success(client, unit):
    tray = Tray.objects.create(
        unit=unit,
        tray_name="Old Tray",
        max_capacity=5
    )

    url = reverse("edit_tray", args=[tray.id])

    data = {
        "tray_name": "Updated Tray",
        "max_capacity": 20,
        "remarks": "Updated remarks"
    }

    response = client.post(url, data)

    assert response.status_code == 302

    tray.refresh_from_db()
    assert tray.tray_name == "Updated Tray"
    assert tray.max_capacity == 20
    assert tray.remarks == "Updated remarks"


# -----------------------------
# Test: Delete Tray Success
# -----------------------------
def test_delete_tray_success(client, unit):
    tray = Tray.objects.create(unit=unit, tray_name="Delete Tray")

    url = reverse("delete_tray", args=[tray.id])
    response = client.post(url)

    assert response.status_code == 302
    assert Tray.objects.filter(id=tray.id).count() == 0


# -----------------------------
# Test: Delete Tray Blocked by TrayTool
# -----------------------------
def test_delete_tray_with_tools(client, unit):
    tray = Tray.objects.create(unit=unit, tray_name="Tool Tray")
    TrayTool.objects.create(
        tray=tray,
        tool_id="TL-001",
        assigned_quantity=1
    )

    url = reverse("delete_tray", args=[tray.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Cannot delete this tray. Tools are assigned to this tray." in messages
    assert Tray.objects.filter(id=tray.id).exists()


# -----------------------------
# Test: Delete Tray Blocked by JobToolUsage
# -----------------------------
def test_delete_tray_assigned_to_jobcard(client, unit):
    tray = Tray.objects.create(unit=unit, tray_name="Job Tray")
    JobToolUsage.objects.create(tray=tray)

    url = reverse("delete_tray", args=[tray.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Tray cannot be deleted. It is associated with one or more Job Cards." in messages
    assert Tray.objects.filter(id=tray.id).exists()
