@pytest.mark.django_db
def test_create_expense():
    user = AppUser.objects.create_user(username="test", password="1234")
    client = APIClient()

    res = client.post("/api/login/", {
        "username": "test",
        "password": "1234"
    }, format="json")

    token = res.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post("/api/expenses/", {
        "categoryKey": "FOOD",
        "amount": 500,
        "date": "2026-04-01"
    }, format="json")

    assert response.status_code == 201

@pytest.mark.django_db
def test_delete_expense():
    user = AppUser.objects.create_user(username="test", password="1234")
    client = APIClient()

    res = client.post("/api/login/", {
        "username": "test",
        "password": "1234"
    }, format="json")

    token = res.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    expense = client.post("/api/expenses/", {
        "categoryKey": "FOOD",
        "amount": 300,
        "date": "2026-04-01"
    }, format="json").data

    delete_res = client.delete(f"/api/expenses/{expense['id']}/")

    assert delete_res.status_code == 204

@pytest.mark.django_db
def test_update_expense():
    user = AppUser.objects.create_user(username="test", password="1234")
    client = APIClient()

    res = client.post("/api/login/", {
        "username": "test",
        "password": "1234"
    }, format="json")

    token = res.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    expense = client.post("/api/expenses/", {
        "categoryKey": "FOOD",
        "amount": 300,
        "date": "2026-04-01"
    }, format="json").data

    update_res = client.put(f"/api/expenses/{expense['id']}/", {
        "categoryKey": "FOOD",
        "amount": 800,
        "date": "2026-04-01"
    }, format="json")

    assert update_res.status_code == 200