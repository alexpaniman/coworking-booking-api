from datetime import datetime, timedelta
from decimal import Decimal

from app.schemas import PriceBreakdown, RecommendationOption
from app.services.smart_booking import create_option_token
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
    assert first_period["options"][0]["quote_expires_at"]


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


def test_smart_booking_uses_quoted_price_even_if_rules_change(client, admin_headers, user_headers):
    location = create_location(client, admin_headers)
    create_room(client, admin_headers, location["id"], price=Decimal("100.00"))
    start_at = future_datetime(hour=14)

    options_response = client.post(
        "/smart-booking/options",
        headers=user_headers,
        json={
            "date": start_at.date().isoformat(),
            "earliest_start": "14:00:00",
            "latest_end": "15:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "location_id": location["id"],
        },
    )
    assert options_response.status_code == 200, options_response.text
    option = options_response.json()["periods"][0]["options"][0]
    quoted_price = option["price"]

    rule_response = client.post(
        "/pricing-rules",
        headers=admin_headers,
        json={
            "name": "Last minute surge",
            "multiplier": "3.00",
            "priority": 500,
            "room_type": "workspace",
            "weekday": start_at.weekday(),
            "start_time": "13:00:00",
            "end_time": "16:00:00",
        },
    )
    assert rule_response.status_code == 201, rule_response.text

    booking_response = client.post(
        "/smart-booking/book",
        headers=user_headers,
        json={"option_token": option["option_token"]},
    )

    assert booking_response.status_code == 201, booking_response.text
    assert booking_response.json()["total_price"] == quoted_price
    assert booking_response.json()["price_breakdown"]["final_price"] == quoted_price


def test_smart_booking_rejects_expired_quote(client, user_headers):
    start_at = future_datetime(hour=17)
    expired_at = datetime.utcnow() - timedelta(minutes=1)
    option = RecommendationOption(
        room_id=1,
        room_name="Expired Room",
        room_type="workspace",
        location_id=1,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
        price=Decimal("100.00"),
        price_breakdown=PriceBreakdown(
            base_price=Decimal("100.00"),
            duration_hours=Decimal("1.00"),
            room_type_multiplier=Decimal("1.00"),
            pricing_rule_multiplier=Decimal("1.00"),
            occupancy_multiplier=Decimal("1.00"),
            final_price=Decimal("100.00"),
        ),
        score=95.0,
    )
    token = create_option_token(option, people_count=2, expires_at=expired_at)

    response = client.post(
        "/smart-booking/book",
        headers=user_headers,
        json={"option_token": token},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Smart booking quote expired"
