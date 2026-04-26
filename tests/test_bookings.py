from datetime import timedelta

from tests.conftest import create_location, create_room, future_datetime


def test_booking_creation_conflict_and_cancel(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"])
    start_at = future_datetime(hour=10)
    end_at = start_at + timedelta(hours=2)

    response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "people_count": 4,
        },
    )
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "confirmed"

    conflict_response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": (start_at + timedelta(minutes=30)).isoformat(),
            "end_at": (end_at + timedelta(minutes=30)).isoformat(),
            "people_count": 4,
        },
    )
    assert conflict_response.status_code == 409

    cancel_response = client.post(f"/bookings/{booking['id']}/cancel", headers=user_headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    retry_response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "people_count": 4,
        },
    )
    assert retry_response.status_code == 201, retry_response.text


def test_booking_validates_capacity_and_time(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"])
    start_at = future_datetime(hour=13)

    capacity_response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=1)).isoformat(),
            "people_count": 99,
        },
    )
    assert capacity_response.status_code == 400

    time_response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": start_at.isoformat(),
            "people_count": 2,
        },
    )
    assert time_response.status_code == 400

