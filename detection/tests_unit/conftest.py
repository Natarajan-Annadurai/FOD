import pytest
from django.contrib.auth.models import User
from django.test import Client

@pytest.fixture
def client(db):
    user = User.objects.create_user(username="testuser", password="pass123")
    client = Client()
    client.login(username="testuser", password="pass123")
    return client
