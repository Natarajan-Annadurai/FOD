import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client

from detection.models import (
    ServiceStation,
    Unit,
    Tray,
    JobCard,
    Aircraft,
    JobToolUsage
)

pytestmark = pytest.mark.django_db


# -----------------------------
# Authenticated client fixture
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
    return ServiceStation.objects.create(name="Station A", location="Chennai")


@pytest.fixture
def incharge():
    return User.objects.create_user(username="unit_incharge", password="pass123")


# -----------------------------
# Test: GET Unit Page
# -----------------------------
def test_create_unit_page_get(client, station):
    url = reverse("create_unit", args=[station.id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"Add Unit to Service Station" in response.content


# -----------------------------
# Test: Create Unit Success
# -----------------------------
def test_create_unit_success(client, station, incharge):
    url = reverse("create_unit", args=[station.id])

    data = {
        "unit_name": "Hydraulics Unit",
        "incharge": incharge.id,
        "remarks": "Handles hydraulics"
    }

    response = client.post(url, data)

    assert response.status_code == 302
    unit = Unit.objects.get(name="Hydraulics Unit")

    assert unit.station == station
    assert unit.incharge == incharge
    assert unit.remarks == "Handles hydraulics"


# -----------------------------
# Test: Edit Unit Success
# -----------------------------
def test_edit_unit_success(client, station, incharge):
    unit = Unit.objects.create(
        station=station,
        name="Old Unit",
        remarks="Old remarks"
    )

    url = reverse("create_unit", args=[station.id])

    data = {
        "unit_id": unit.id,
        "unit_name": "Updated Unit",
        "incharge": incharge.id,
        "remarks": "Updated remarks"
    }

    response = client.post(url, data)

    assert response.status_code == 302

    unit.refresh_from_db()
    assert unit.name == "Updated Unit"
    assert unit.incharge == incharge
    assert unit.remarks == "Updated remarks"


# -----------------------------
# Test: Delete Unit Success
# -----------------------------
def test_delete_unit_success(client, station):
    unit = Unit.objects.create(station=station, name="Delete Unit")

    url = reverse("delete_unit", args=[station.id, unit.id])
    response = client.post(url)

    assert response.status_code == 302
    assert Unit.objects.filter(id=unit.id).count() == 0


# -----------------------------
# Test: Delete Unit Blocked by Tray
# -----------------------------
def test_delete_unit_with_trays(client, station):
    unit = Unit.objects.create(station=station, name="Tray Unit")
    Tray.objects.create(unit=unit, name="Tray 1")

    url = reverse("delete_unit", args=[station.id, unit.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Cannot delete this Unit. Trays are assigned under this unit." in messages
    assert Unit.objects.filter(id=unit.id).exists()


# -----------------------------
# Test: Delete Unit Blocked by JobCard
# -----------------------------
def test_delete_unit_assigned_to_jobcard(client, station):
    unit = Unit.objects.create(station=station, name="JobCard Unit")
    aircraft = Aircraft.objects.create(
        aircraft_id="AC-200",
        registration_no="REG-200",
        model="A320"
    )

    jobcard = JobCard.objects.create(
        job_number="JOB-200",
        aircraft=aircraft
    )
    jobcard.assigned_units.add(unit)

    url = reverse("delete_unit", args=[station.id, unit.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Unit cannot be deleted. It is assigned to one or more Job Cards." in messages
    assert Unit.objects.filter(id=unit.id).exists()


# -----------------------------
# Test: Delete Unit Blocked by Tool Usage
# -----------------------------
def test_delete_unit_used_in_tool_usage(client, station):
    unit = Unit.objects.create(station=station, name="Tool Usage Unit")
    JobToolUsage.objects.create(unit=unit)

    url = reverse("delete_unit", args=[station.id, unit.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Unit cannot be deleted. It is linked to tool usage history." in messages
    assert Unit.objects.filter(id=unit.id).exists()
