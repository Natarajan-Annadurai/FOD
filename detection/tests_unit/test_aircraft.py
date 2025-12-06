import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client
from detection.models import Aircraft, JobCard

pytestmark = pytest.mark.django_db

@pytest.fixture
def client():
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client

# -----------------------------
# Test: GET Aircraft List
# -----------------------------
def test_aircraft_list_get(client):
    url = reverse('aircraft_list')
    response = client.get(url)
    assert response.status_code == 200
    assert b"Aircraft Fleet Management" in response.content

# -----------------------------
# Test: POST Aircraft Creation Success
# -----------------------------
def test_aircraft_creation_success(client):
    url = reverse('aircraft_list')
    data = {
        "aircraft_id": "AC-001",
        "registration_no": "REG-001",
        "model": "A320",
        "manufacturer": "Airbus",
        "airline_name": "SkyAir",
        "flight_hours": 100,
        "flight_cycles": 50,
        "remarks": "Test aircraft"
    }
    response = client.post(url, data)
    assert response.status_code == 302  # Redirect to aircraft_list
    aircraft = Aircraft.objects.get(aircraft_id="AC-001")
    assert aircraft.registration_no == "REG-001"

# -----------------------------
# Test: POST Aircraft Creation Duplicate ID
# -----------------------------
def test_aircraft_creation_duplicate(client):
    Aircraft.objects.create(aircraft_id="AC-001", registration_no="REG-001", model="A320")
    url = reverse('aircraft_list')
    data = {
        "aircraft_id": "AC-001",
        "registration_no": "REG-002",
        "model": "B737",
    }
    response = client.post(url, data, follow=True)
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert "Aircraft ID 'AC-001' already exists." in messages

# -----------------------------
# Test: Aircraft Edit Success
# -----------------------------
def test_aircraft_edit_success(client):
    aircraft = Aircraft.objects.create(aircraft_id="AC-001", registration_no="REG-001", model="A320")
    url = reverse('aircraft_edit', args=[aircraft.id])
    data = {
        "aircraft_id": "AC-002",
        "registration_no": "REG-002",
        "model": "B737",
        "manufacturer": "Boeing",
        "airline_name": "FlyHigh",
        "flight_hours": 200,
        "flight_cycles": 100,
        "remarks": "Updated"
    }
    response = client.post(url, data)
    assert response.status_code == 302
    aircraft.refresh_from_db()
    assert aircraft.aircraft_id == "AC-002"
    assert aircraft.registration_no == "REG-002"

# -----------------------------
# Test: Aircraft Edit Duplicate Registration No
# -----------------------------
def test_aircraft_edit_duplicate_reg(client):
    Aircraft.objects.create(aircraft_id="AC-001", registration_no="REG-001", model="A320")
    aircraft2 = Aircraft.objects.create(aircraft_id="AC-002", registration_no="REG-002", model="B737")
    url = reverse('aircraft_edit', args=[aircraft2.id])
    data = {
        "aircraft_id": "AC-002",
        "registration_no": "REG-001",  # duplicate
        "model": "B737"
    }
    response = client.post(url, data, follow=True)
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert "Aircraft with registration 'REG-001' already exists." in messages

# -----------------------------
# Test: Aircraft Delete Success
# -----------------------------
def test_aircraft_delete_success(client):
    aircraft = Aircraft.objects.create(aircraft_id="AC-001", registration_no="REG-001", model="A320")
    url = reverse('aircraft_delete', args=[aircraft.id])
    response = client.post(url)
    assert response.status_code == 302
    assert Aircraft.objects.filter(id=aircraft.id).count() == 0
