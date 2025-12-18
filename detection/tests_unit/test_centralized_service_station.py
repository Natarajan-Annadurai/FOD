import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from centralized.models import ServiceStation, Unit, Tray, JobCard

pytestmark = pytest.mark.django_db

@pytest.fixture
def client():
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client

def test_centralized_dashboard_get(client):
    url = reverse("centralized_system_monitoring")
    response = client.get(url)

    assert response.status_code == 200
    assert b"Service Station" in response.content or b"Centralized" in response.content

def test_service_station_report_get(client):
    station = ServiceStation.objects.create(
        name="Main Station",
        location="Chennai",
        contact_email="station@test.com"
    )

    url = reverse("service_station_report", args=[station.id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"Service Station Report" in response.content
    assert station.name.encode() in response.content

def test_service_station_report_invalid_id(client):
    url = reverse("service_station_report", args=[999])
    response = client.get(url)

    assert response.status_code == 404

def test_station_units_and_trays_render(client):
    station = ServiceStation.objects.create(
        name="Station A", location="BLR", contact_email="a@test.com"
    )

    unit = Unit.objects.create(
        name="Engine Unit", station=station
    )

    tray = Tray.objects.create(
        tray_name="Tray A", unit=unit, status="ACTIVE"
    )

    url = reverse("service_station_report", args=[station.id])
    response = client.get(url)

    assert b"Engine Unit" in response.content
    assert b"Tray A" in response.content
    assert b"ACTIVE" in response.content

def test_station_jobcard_render(client):
    station = ServiceStation.objects.create(
        name="Station B", location="HYD", contact_email="b@test.com"
    )

    unit = Unit.objects.create(name="Unit 1", station=station)

    jobcard = JobCard.objects.create(
        job_id="JC-001",
        job_title="Inspection",
        status="CREATED",
        service_station=station
    )
    jobcard.assigned_units.add(unit)

    url = reverse("service_station_report", args=[station.id])
    response = client.get(url)

    assert b"JC-001" in response.content
    assert b"Inspection" in response.content
    assert b"CREATED" in response.content

def test_station_no_jobcards_message(client):
    station = ServiceStation.objects.create(
        name="Empty Station",
        location="DEL",
        contact_email="empty@test.com"
    )

    url = reverse("service_station_report", args=[station.id])
    response = client.get(url)

    assert b"No jobcards found" in response.content

def test_service_station_pdf_view(client):
    station = ServiceStation.objects.create(
        name="PDF Station",
        location="Pune",
        contact_email="pdf@test.com"
    )

    url = reverse("service_station_report_pdf", args=[station.id])
    response = client.get(url)

    assert response.status_code in (200, 302)

def test_service_station_login_required():
    station = ServiceStation.objects.create(
        name="Secure Station",
        location="Mumbai",
        contact_email="secure@test.com"
    )

    client = Client()
    url = reverse("service_station_report", args=[station.id])
    response = client.get(url)

    assert response.status_code in (302, 403)




