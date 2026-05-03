#!/usr/bin/env python3
import argparse
import json
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable


JsonObject = dict[str, Any]
ResponseView = Callable[[Any], Any]


@dataclass
class DemoState:
    base_url: str
    run_suffix: str
    admin_email: str
    user_email: str
    admin_token: str | None = None
    user_token: str | None = None
    location_id: int | None = None
    amenity_id: int | None = None
    workspace_room_id: int | None = None
    meeting_room_id: int | None = None
    booking_id: int | None = None
    smart_option_token: str | None = None


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: JsonObject | None = None,
        form_body: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        data = None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")
        if form_body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urllib.parse.urlencode(form_body).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, read_response(response)
        except urllib.error.HTTPError as exc:
            return exc.code, read_response(exc)


def read_response(response: Any) -> Any:
    body = response.read().decode("utf-8")
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def pretty_json(value: Any) -> str:
    if value is None:
        return "<empty response>"
    return json.dumps(value, indent=2, ensure_ascii=False)


def shorten_token(token: str) -> str:
    if len(token) <= 48:
        return token
    return f"{token[:24]}...{token[-8:]}"


def redact_tokens(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: shorten_token(item) if key in {"access_token", "option_token"} else redact_tokens(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_tokens(item) for item in value]
    return value


def compact_recommendations(body: Any) -> Any:
    if not isinstance(body, dict) or "options" not in body:
        return body
    return {
        "options_count": len(body["options"]),
        "options": body["options"][:3],
    }


def compact_smart_options(body: Any) -> Any:
    if not isinstance(body, dict) or "periods" not in body:
        return body

    periods = []
    for period in body["periods"][:2]:
        period_copy = dict(period)
        period_copy["options"] = period_copy.get("options", [])[:2]
        periods.append(period_copy)

    return {
        "periods_count": len(body["periods"]),
        "periods": periods,
    }


def print_block(title: str, text: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)
    print(textwrap.dedent(text).strip())


def wait_for_enter(auto: bool) -> None:
    if auto:
        return
    input("\nPress Enter to run this step...")


def print_request(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: JsonObject | None = None,
    form_body: dict[str, str] | None = None,
) -> None:
    body = json_body or form_body
    print("\nCommand:")
    print(f"curl -s -X {method} {base_url.rstrip('/')}{path}")
    if token:
        print("-H 'Authorization: Bearer <access_token>'")
    if json_body is not None:
        print("-H 'Content-Type: application/json'")
    if form_body is not None:
        print("-H 'Content-Type: application/x-www-form-urlencoded'")
    if body is not None:
        print(pretty_json(redact_tokens(body)))


def print_response(status_code: int, body: Any, response_view: ResponseView | None = None) -> None:
    display_body = response_view(body) if response_view else body
    print("\nResponse:")
    print(f"HTTP {status_code}")
    print(pretty_json(redact_tokens(display_body)))


def run_api_step(
    state: DemoState,
    title: str,
    description: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: JsonObject | None = None,
    form_body: dict[str, str] | None = None,
    response_view: ResponseView | None = None,
    auto: bool = False,
) -> tuple[int, Any]:
    print_block(title, description)
    print_request(
        state.base_url,
        method,
        path,
        token=token,
        json_body=json_body,
        form_body=form_body,
    )
    wait_for_enter(auto)
    status_code, body = ApiClient(state.base_url).request(
        method,
        path,
        token=token,
        json_body=json_body,
        form_body=form_body,
    )
    print_response(status_code, body, response_view)
    return status_code, body


def future_iso(days: int, hour: int, minute: int = 0) -> str:
    value = (datetime.utcnow() + timedelta(days=days)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    return value.isoformat()


def future_date(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).date().isoformat()


def require_status(status_code: int, expected: int, step: str) -> None:
    if status_code != expected:
        raise RuntimeError(f"{step} failed: expected HTTP {expected}, got HTTP {status_code}")


def register_user(state: DemoState, role: str, auto: bool) -> None:
    email = state.admin_email if role == "admin" else state.user_email
    status_code, _ = run_api_step(
        state,
        f"Register {role}",
        f"""
        Creates a {role} account. Passwords are hashed with passlib + bcrypt;
        plain text passwords are never stored in the database.
        """,
        "POST",
        "/auth/register",
        json_body={
            "email": email,
            "password": "secret123",
            "full_name": role.title(),
            "role": role,
        },
        auto=auto,
    )
    if status_code not in {201, 400}:
        raise RuntimeError(f"registration failed for {email}: HTTP {status_code}")


def login_user(state: DemoState, role: str, auto: bool) -> str:
    email = state.admin_email if role == "admin" else state.user_email
    status_code, body = run_api_step(
        state,
        f"Login {role} and get JWT",
        """
        Login returns a JWT access token. Later protected requests send it as:
        Authorization: Bearer <access_token>
        """,
        "POST",
        "/auth/login",
        form_body={"username": email, "password": "secret123"},
        auto=auto,
    )
    require_status(status_code, 200, f"login {email}")
    return body["access_token"]


def run_demo(auto: bool, base_url: str) -> None:
    run_suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    state = DemoState(
        base_url=base_url,
        run_suffix=run_suffix,
        admin_email=f"demo-admin-{run_suffix}@example.com",
        user_email=f"demo-user-{run_suffix}@example.com",
    )

    run_api_step(
        state,
        "Health check",
        "Checks that the FastAPI application is running.",
        "GET",
        "/health",
        auto=auto,
    )

    register_user(state, "admin", auto)
    register_user(state, "user", auto)
    state.admin_token = login_user(state, "admin", auto)
    state.user_token = login_user(state, "user", auto)

    status_code, body = run_api_step(
        state,
        "Protected endpoint",
        "Shows that JWT works: /users/me returns the current user from the access token.",
        "GET",
        "/users/me",
        token=state.user_token,
        auto=auto,
    )
    require_status(status_code, 200, "users/me")

    status_code, body = run_api_step(
        state,
        "Admin creates a location",
        "Locations define coworking branches and working hours.",
        "POST",
        "/locations",
        token=state.admin_token,
        json_body={
            "name": f"Demo Hub {state.run_suffix}",
            "address": "Demo street 1",
            "opens_at": "09:00:00",
            "closes_at": "20:00:00",
        },
        auto=auto,
    )
    require_status(status_code, 201, "create location")
    state.location_id = body["id"]

    status_code, body = run_api_step(
        state,
        "Admin creates an amenity",
        "Amenities are linked to rooms through a many-to-many table.",
        "POST",
        "/amenities",
        token=state.admin_token,
        json_body={
            "name": f"Demo whiteboard {state.run_suffix}",
            "description": "Board for team sessions",
        },
        auto=auto,
    )
    require_status(status_code, 201, "create amenity")
    state.amenity_id = body["id"]

    status_code, body = run_api_step(
        state,
        "Admin creates a workspace room",
        "This room has a 15 minute buffer between bookings.",
        "POST",
        "/rooms",
        token=state.admin_token,
        json_body={
            "location_id": state.location_id,
            "name": f"Demo Open Space {state.run_suffix}",
            "room_type": "workspace",
            "capacity": 6,
            "base_price_per_hour": "500.00",
            "buffer_minutes": 15,
            "description": "Shared workspace",
            "amenity_ids": [state.amenity_id],
        },
        auto=auto,
    )
    require_status(status_code, 201, "create workspace room")
    state.workspace_room_id = body["id"]

    status_code, body = run_api_step(
        state,
        "Admin creates a meeting room",
        "A second room makes recommendations and smart booking more interesting.",
        "POST",
        "/rooms",
        token=state.admin_token,
        json_body={
            "location_id": state.location_id,
            "name": f"Demo Focus Room {state.run_suffix}",
            "room_type": "meeting_room",
            "capacity": 4,
            "base_price_per_hour": "900.00",
            "buffer_minutes": 10,
            "description": "Quiet meeting room",
            "amenity_ids": [state.amenity_id],
        },
        auto=auto,
    )
    require_status(status_code, 201, "create meeting room")
    state.meeting_room_id = body["id"]

    status_code, _ = run_api_step(
        state,
        "Admin creates a pricing rule",
        "This rule increases prices during peak working hours.",
        "POST",
        "/pricing-rules",
        token=state.admin_token,
        json_body={
            "name": f"Demo peak hours {state.run_suffix}",
            "multiplier": "1.40",
            "priority": 300,
            "location_id": state.location_id,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
        },
        auto=auto,
    )
    require_status(status_code, 201, "create pricing rule")

    booking_start = future_iso(days=7, hour=10)
    booking_end = future_iso(days=7, hour=11)
    status_code, body = run_api_step(
        state,
        "User creates a booking",
        """
        The response includes total_price and price_breakdown, so the dynamic
        price is explainable.
        """,
        "POST",
        "/bookings",
        token=state.user_token,
        json_body={
            "room_id": state.workspace_room_id,
            "start_at": booking_start,
            "end_at": booking_end,
            "people_count": 3,
        },
        auto=auto,
    )
    require_status(status_code, 201, "create booking")
    state.booking_id = body["id"]

    status_code, _ = run_api_step(
        state,
        "Conflict check",
        """
        This tries to book the same room at an overlapping time.
        The API should reject it with HTTP 409.
        """,
        "POST",
        "/bookings",
        token=state.user_token,
        json_body={
            "room_id": state.workspace_room_id,
            "start_at": future_iso(days=7, hour=10, minute=30),
            "end_at": future_iso(days=7, hour=11, minute=30),
            "people_count": 2,
        },
        auto=auto,
    )
    require_status(status_code, 409, "conflict check")

    status_code, body = run_api_step(
        state,
        "Reschedule booking",
        "Moves the booking and recalculates the price with the same validation rules.",
        "PATCH",
        f"/bookings/{state.booking_id}/reschedule",
        token=state.user_token,
        json_body={
            "start_at": future_iso(days=7, hour=12),
            "end_at": future_iso(days=7, hour=13),
            "people_count": 3,
        },
        auto=auto,
    )
    require_status(status_code, 200, "reschedule booking")

    status_code, _ = run_api_step(
        state,
        "Recommendations",
        """
        The algorithm splits the day into 30 minute slots, removes busy slots,
        filters by capacity, location, amenities and budget, then sorts by score.
        """,
        "POST",
        "/recommendations/booking-options",
        token=state.user_token,
        json_body={
            "date": future_date(days=7),
            "earliest_start": "09:00:00",
            "latest_end": "15:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "need_meeting_room": False,
            "location_id": state.location_id,
            "max_price": "2000.00",
            "amenity_ids": [state.amenity_id],
        },
        response_view=compact_recommendations,
        auto=auto,
    )
    require_status(status_code, 200, "recommendations")

    status_code, body = run_api_step(
        state,
        "Smart booking options",
        """
        Smart booking is for the case where the user cares about time, price
        and capacity, but does not need to choose a room manually.
        Each option includes a signed option_token and quote_expires_at.
        """,
        "POST",
        "/smart-booking/options",
        token=state.user_token,
        json_body={
            "date": future_date(days=7),
            "earliest_start": "14:00:00",
            "latest_end": "18:00:00",
            "duration_minutes": 60,
            "people_count": 2,
            "need_meeting_room": False,
            "location_id": state.location_id,
            "max_price": "2000.00",
        },
        response_view=compact_smart_options,
        auto=auto,
    )
    require_status(status_code, 200, "smart booking options")
    state.smart_option_token = body["periods"][0]["options"][0]["option_token"]

    status_code, _ = run_api_step(
        state,
        "Smart booking confirm",
        """
        The selected option_token locks the quoted price for 5 minutes.
        Availability is checked again before the booking is created.
        """,
        "POST",
        "/smart-booking/book",
        token=state.user_token,
        json_body={"option_token": state.smart_option_token},
        auto=auto,
    )
    require_status(status_code, 201, "smart booking confirm")

    status_code, _ = run_api_step(
        state,
        "Quote reuse / synchronization check",
        """
        Reusing the same option_token should fail because the slot was just booked.
        This demonstrates synchronization: options are revalidated at booking time.
        """,
        "POST",
        "/smart-booking/book",
        token=state.user_token,
        json_body={"option_token": state.smart_option_token},
        auto=auto,
    )
    require_status(status_code, 409, "quote reuse")

    status_code, _ = run_api_step(
        state,
        "Cancel booking",
        "Cancels the original booking and sends a Telegram notification if enabled.",
        "POST",
        f"/bookings/{state.booking_id}/cancel",
        token=state.user_token,
        auto=auto,
    )
    require_status(status_code, 200, "cancel booking")

    print_block(
        "Demo complete",
        """
        The scenario covered:
        - JWT auth and roles
        - admin CRUD
        - booking validation
        - conflict prevention
        - dynamic price breakdown
        - recommendations
        - smart booking with quoted price lock
        - cancellation and Telegram notification hook
        """,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive demo runner for Coworking Booking API.")
    parser.add_argument("--auto", action="store_true", help="Run without waiting for Enter between steps.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL.")
    return parser.parse_args()


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    try:
        run_demo(auto=args.auto, base_url=args.base_url)
    except (RuntimeError, urllib.error.URLError) as error:
        print(f"\nDemo failed: {error}", file=sys.stderr)
        sys.exit(1)
