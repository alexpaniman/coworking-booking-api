from datetime import timedelta
from decimal import Decimal

from tests.conftest import create_amenity, create_location, create_room, future_datetime


def test_recommendations_skip_busy_slots_and_apply_dynamic_price(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    amenity = create_amenity(client, admin_headers, "Whiteboard")
    room = create_room(
        client,
        admin_headers,
        location["id"],
        [amenity["id"]],
        price=Decimal("100.00"),
    )
    create_room(
        client,
        admin_headers,
        location["id"],
        [amenity["id"]],
        room_type="meeting_room",
        name="Focus Room",
        price=Decimal("200.00"),
    )

    start_at = future_datetime(hour=11)
    client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=1)).isoformat(),
            "people_count": 2,
        },
    )

    rule_response = client.post(
        "/pricing-rules",
        headers=admin_headers,
        json={
            "name": "Peak day",
            "multiplier": "2.00",
            "priority": 300,
            "room_type": "workspace",
            "weekday": start_at.weekday(),
            "start_time": "09:00:00",
            "end_time": "18:00:00",
        },
    )
    assert rule_response.status_code == 201, rule_response.text

    response = client.post(
        "/recommendations/booking-options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "09:00:00",
            "latest_end": "13:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "need_meeting_room": False,
            "location_id": location["id"],
            "amenity_ids": [amenity["id"]],
        },
    )

    assert response.status_code == 200, response.text
    options = response.json()["options"]
    assert options
    assert all(not (option["room_id"] == room["id"] and option["start_at"].endswith("11:00:00")) for option in options)
    workspace_prices = [
        Decimal(str(option["price"]))
        for option in options
        if option["room_id"] == room["id"]
    ]
    assert workspace_prices
    assert max(workspace_prices) > Decimal("200.00")


def test_recommendations_respect_budget(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"], price=Decimal("1000.00"))
    start_at = future_datetime(hour=9)

    response = client.post(
        "/recommendations/booking-options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "09:00:00",
            "latest_end": "12:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
            "max_price": "100.00",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["options"] == []
    assert room["id"]


def test_recommendations_respect_location_working_hours(client, admin_headers, user_headers):
    location = create_location(client, admin_headers, opens_at="10:00:00", closes_at="12:00:00")
    create_room(client, admin_headers, location["id"], price=Decimal("100.00"))
    start_at = future_datetime(hour=9)

    response = client.post(
        "/recommendations/booking-options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "09:00:00",
            "latest_end": "13:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
        },
    )

    assert response.status_code == 200, response.text
    start_times = {option["start_at"][-8:] for option in response.json()["options"]}
    assert start_times == {"10:00:00", "10:30:00", "11:00:00"}


def test_recommendations_respect_room_buffer(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"], price=Decimal("100.00"), buffer_minutes=30)
    start_at = future_datetime(hour=10)
    booking_response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=1)).isoformat(),
            "people_count": 2,
        },
    )
    assert booking_response.status_code == 201, booking_response.text

    response = client.post(
        "/recommendations/booking-options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "09:00:00",
            "latest_end": "12:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
        },
    )

    assert response.status_code == 200, response.text
    start_times = {option["start_at"][-8:] for option in response.json()["options"]}
    assert "09:00:00" not in start_times
    assert "11:00:00" not in start_times
