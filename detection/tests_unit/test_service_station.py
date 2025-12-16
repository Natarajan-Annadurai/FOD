import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client

from detection.models import ServiceStation, JobCard, Aircraft

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
# Test: GET Service Station List
# -----------------------------
def test_service_station_list_get(client):
    url = reverse("service_station_list")
    response = client.get(url)

    assert response.status_code == 200
    assert b"Service Stations" in response.content


# -----------------------------
# Test: Create Service Station Success
# -----------------------------
def test_create_service_station_success(client):
    manager = User.objects.create_user(username="manager1", password="pass123")
    url = reverse("create_service_station")

    data = {
        "name": "Station A",
        "location": "Chennai",
        "manager": manager.id,
        "remarks": "Main station"
    }

    response = client.post(url, data)

    assert response.status_code == 302
    station = ServiceStation.objects.get(name="Station A")
    assert station.location == "Chennai"
    assert station.manager == manager


# -----------------------------
# Test: Edit Service Station (AJAX JSON)
# -----------------------------
def test_edit_service_station_success(client):
    manager = User.objects.create_user(username="manager2", password="pass123")
    station = ServiceStation.objects.create(
        name="Old Station",
        location="Delhi"
    )

    url = reverse("edit_service_station", args=[station.id])

    payload = {
        "name": "Updated Station",
        "location": "Mumbai",
        "manager": manager.username
    }

    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert response.status_code == 200

    station.refresh_from_db()
    assert station.name == "Updated Station"
    assert station.location == "Mumbai"
    assert station.manager == manager


# -----------------------------
# Test: Edit Service Station Invalid Method
# -----------------------------
def test_edit_service_station_invalid_method(client):
    station = ServiceStation.objects.create(name="Station X")

    url = reverse("edit_service_station", args=[station.id])
    response = client.get(url)

    assert response.status_code == 200
    assert response.json()["status"] == "invalid request"


# -----------------------------
# Test: Delete Service Station Success
# -----------------------------
def test_delete_service_station_success(client):
    station = ServiceStation.objects.create(name="Delete Me")

    url = reverse("delete_service_station", args=[station.id])
    response = client.post(url)

    assert response.status_code == 302
    assert ServiceStation.objects.filter(id=station.id).count() == 0


# -----------------------------
# Test: Delete Service Station Assigned to JobCard
# -----------------------------
def test_delete_service_station_assigned_to_jobcard(client):
    station = ServiceStation.objects.create(name="Assigned Station")
    aircraft = Aircraft.objects.create(
        aircraft_id="AC-100",
        registration_no="REG-100",
        model="A320"
    )

    JobCard.objects.create(
        job_number="JOB-001",
        aircraft=aircraft,
        service_station=station
    )

    url = reverse("delete_service_station", args=[station.id])
    response = client.post(url, follow=True)

    messages = [m.message for m in get_messages(response.wsgi_request)]

    assert "Cannot delete. This service station is assigned to one or more job cards." in messages
    assert ServiceStation.objects.filter(id=station.id).exists()
