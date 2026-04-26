from tests.conftest import login_headers, register_user


def test_register_login_and_read_current_user(client):
    user = register_user(client, "alice@example.com")
    assert user["email"] == "alice@example.com"
    assert user["role"] == "user"

    headers = login_headers(client, "alice@example.com")
    response = client.get("/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_protected_endpoint_requires_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401

