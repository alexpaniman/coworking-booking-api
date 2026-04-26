from tests.conftest import create_amenity, create_location, create_room, register_user, login_headers


def test_user_cannot_manage_admin_resources(client, user_headers):
    response = client.post(
        "/locations",
        headers=user_headers,
        json={"name": "Forbidden Hub", "address": "Hidden street 1"},
    )

    assert response.status_code == 403


def test_admin_can_manage_locations_amenities_rooms_and_pricing_rules(client, admin_headers):
    location = create_location(client, admin_headers)
    amenity = create_amenity(client, admin_headers)
    room = create_room(client, admin_headers, location["id"], [amenity["id"]])

    assert room["name"] == "Open Space A"
    assert room["amenities"][0]["name"] == "Projector"

    patch_response = client.patch(
        f"/rooms/{room['id']}",
        headers=admin_headers,
        json={"capacity": 8},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["capacity"] == 8

    rule_response = client.post(
        "/pricing-rules",
        headers=admin_headers,
        json={
            "name": "Evening peak",
            "multiplier": "1.30",
            "priority": 200,
            "room_type": "workspace",
            "start_time": "18:00:00",
            "end_time": "21:00:00",
        },
    )
    assert rule_response.status_code == 201, rule_response.text
    assert rule_response.json()["multiplier"] == "1.30"

    delete_response = client.delete(f"/rooms/{room['id']}", headers=admin_headers)
    assert delete_response.status_code == 204


def test_duplicate_email_is_rejected(client):
    register_user(client, "duplicate@example.com")
    response = client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "secret123",
            "role": "user",
        },
    )

    assert response.status_code == 400


def test_login_rejects_wrong_password(client):
    register_user(client, "bad-login@example.com")
    response = client.post(
        "/auth/login",
        data={"username": "bad-login@example.com", "password": "wrong"},
    )

    assert response.status_code == 401

