import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from detection.models import JobCard

pytestmark = pytest.mark.django_db

@pytest.fixture
def client():
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client


@pytest.fixture
def jobcard():
    return JobCard.objects.create(
        job_id="JOB-001",
        aircraft_id="AC-001",
        issue_description="Engine vibration",
        status="Open"
    )

def test_jobcard_list_page_get(client):
    url = reverse("jobcard_list")
    response = client.get(url)

    assert response.status_code == 200
    assert b"Job Cards" in response.content

def test_jobcard_create_success(client):
    url = reverse("jobcard_create")
    data = {
        "job_id": "JOB-002",
        "aircraft_id": "AC-002",
        "issue_description": "Hydraulic leak",
        "status": "Open"
    }
    response = client.post(url, data)

    assert response.status_code == 302
    assert JobCard.objects.filter(job_id="JOB-002").exists()

def test_jobcard_create_duplicate_job_id(client, jobcard):
    url = reverse("jobcard_create")
    data = {
        "job_id": "JOB-001",  # duplicate
        "aircraft_id": "AC-003",
        "issue_description": "Duplicate test",
        "status": "Open"
    }
    response = client.post(url, data, follow=True)

    assert b"already exists" in response.content

def test_jobcard_edit_success(client, jobcard):
    url = reverse("jobcard_edit", args=[jobcard.job_id])
    data = {
        "job_id": jobcard.job_id,
        "aircraft_id": "AC-009",
        "issue_description": "Updated issue",
        "status": "Closed"
    }
    response = client.post(url, data)

    assert response.status_code == 302
    jobcard.refresh_from_db()
    assert jobcard.status == "Closed"

def test_jobcard_delete_success(client, jobcard):
    url = reverse("jobcard_delete", args=[jobcard.job_id])
    response = client.post(url)

    assert response.status_code == 302
    assert not JobCard.objects.filter(job_id=jobcard.job_id).exists()

def test_jobcard_notes_page(client, jobcard):
    url = reverse("jobcard_notes", args=[jobcard.job_id])
    response = client.get(url)

    assert response.status_code == 200
    assert b"Job Notes" in response.content
    assert jobcard.job_id.encode() in response.content

def test_jobcard_notes_summary_cards(client, jobcard):
    response = client.get(reverse("jobcard_notes", args=[jobcard.job_id]))

    assert b"Total Notes" in response.content
    assert b"Completed" in response.content
    assert b"In Progress" in response.content
    assert b"Pending" in response.content

def test_jobcard_notes_empty_state(client, jobcard):
    response = client.get(reverse("jobcard_notes", args=[jobcard.job_id]))

    assert b"No notes found" in response.content
    assert b"Get started by creating your first job note" in response.content

def test_jobcard_notes_pagination_text(client, jobcard):
    response = client.get(reverse("jobcard_notes", args=[jobcard.job_id]))

    assert b"Showing" in response.content
    assert b"results" in response.content
