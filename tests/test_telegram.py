from datetime import timedelta

from tests.conftest import create_location, create_room, future_datetime


def test_booking_calls_telegram_notification_without_breaking_api(
    client,
    admin_headers,
    user_headers,
    monkeypatch,
):
    calls = []

    def fake_notify(booking, action):
        calls.append((booking.id, action))
        return False

    monkeypatch.setattr("app.routers.bookings.notify_booking", fake_notify)

    location = create_location(client, admin_headers)
    room = create_room(client, admin_headers, location["id"])
    start_at = future_datetime(hour=15)

    response = client.post(
        "/bookings",
        headers=user_headers,
        json={
            "room_id": room["id"],
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=1)).isoformat(),
            "people_count": 3,
        },
    )
    assert response.status_code == 201, response.text

    booking_id = response.json()["id"]
    reschedule_response = client.patch(
        f"/bookings/{booking_id}/reschedule",
        headers=user_headers,
        json={
            "start_at": (start_at + timedelta(hours=2)).isoformat(),
            "end_at": (start_at + timedelta(hours=3)).isoformat(),
        },
    )
    assert reschedule_response.status_code == 200

    cancel_response = client.post(f"/bookings/{booking_id}/cancel", headers=user_headers)
    assert cancel_response.status_code == 200

    assert calls == [(booking_id, "created"), (booking_id, "rescheduled"), (booking_id, "cancelled")]
