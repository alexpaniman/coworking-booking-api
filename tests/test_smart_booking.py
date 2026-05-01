from datetime import timedelta
from decimal import Decimal

from tests.conftest import create_location, create_room, future_datetime


def test_smart_booking_returns_periods_with_signed_options(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    create_room(client, admin_headers, location["id"], name="Open Space A", price=Decimal("100.00"))
    create_room(client, admin_headers, location["id"], name="Focus Room", price=Decimal("150.00"))
    start_at = future_datetime(hour=10)

    response = client.post(
        "/smart-booking/options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "10:00:00",
            "latest_end": "12:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
        },
    )

    assert response.status_code == 200, response.text
    periods = response.json()["periods"]
    assert periods
    first_period = periods[0]
    assert len(first_period["options"]) == 2
    assert first_period["cheapest_price"] == first_period["options"][0]["price"]
    assert first_period["options"][0]["option_token"]


def test_smart_booking_can_book_selected_option_and_revalidates_token(
    client,
    admin_headers,
    user_headers,
):
    location = create_location(client, admin_headers)
    create_room(client, admin_headers, location["id"], price=Decimal("100.00"))
    start_at = future_datetime(hour=13)

    options_response = client.post(
        "/smart-booking/options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "13:00:00",
            "latest_end": "15:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
        },
    )
    assert options_response.status_code == 200, options_response.text
    token = options_response.json()["periods"][0]["options"][0]["option_token"]

    booking_response = client.post(
        "/smart-booking/book",
        headers=user_headers,
        json={"option_token": token},
    )
    assert booking_response.status_code == 201, booking_response.text
    assert booking_response.json()["price_breakdown"]["final_price"] == booking_response.json()["total_price"]

    repeat_response = client.post(
        "/smart-booking/book",
        headers=user_headers,
        json={"option_token": token},
    )
    assert repeat_response.status_code == 409


def test_smart_booking_rejects_tampered_option_token(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"], price=Decimal("100.00"))
    start_at = future_datetime(hour=16)
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
    assert booking_response.status_code == 201

    response = client.post(
        "/smart-booking/book",
        headers=user_headers,
        json={"option_token": "invalid.token"},
    )

    assert response.status_code == 400
