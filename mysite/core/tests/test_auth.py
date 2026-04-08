import pytest
from core.models import AppUser
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_user_login():
    user = AppUser.objects.create_user(username="test", password="1234")

    client = APIClient()
    response = client.post("/api/login/", {
        "username": "test",
        "password": "1234"
    }, format="json")

    assert response.status_code == 200
    assert "access" in response.data