import os
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://coworking:coworking@db:5432/coworking_test",
)
os.environ["SECRET_KEY"] = "test-secret"
os.environ["TELEGRAM_ENABLED"] = "false"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def register_user(client: TestClient, email: str, role: str = "user") -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "secret123",
            "full_name": email.split("@")[0],
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    register_user(client, "admin@example.com", "admin")
    return login_headers(client, "admin@example.com")


@pytest.fixture
def user_headers(client: TestClient) -> dict[str, str]:
    register_user(client, "user@example.com", "user")
    return login_headers(client, "user@example.com")


def future_datetime(days: int = 3, hour: int = 10) -> datetime:
    return (datetime.utcnow() + timedelta(days=days)).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )


def create_location(
    client: TestClient,
    headers: dict[str, str],
    opens_at: str = "08:00:00",
    closes_at: str = "22:00:00",
) -> dict:
    response = client.post(
        "/locations",
        headers=headers,
        json={
            "name": "Center Hub",
            "address": "Main street 1",
            "opens_at": opens_at,
            "closes_at": closes_at,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_amenity(client: TestClient, headers: dict[str, str], name: str = "Projector") -> dict:
    response = client.post(
        "/amenities",
        headers=headers,
        json={"name": name, "description": "Useful for meetings"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_room(
    client: TestClient,
    headers: dict[str, str],
    location_id: int,
    amenity_ids: list[int] | None = None,
    room_type: str = "workspace",
    name: str = "Open Space A",
    price: Decimal = Decimal("500.00"),
    buffer_minutes: int = 0,
) -> dict:
    response = client.post(
        "/rooms",
        headers=headers,
        json={
            "location_id": location_id,
            "name": name,
            "room_type": room_type,
            "capacity": 6,
            "base_price_per_hour": str(price),
            "buffer_minutes": buffer_minutes,
            "description": "Comfortable coworking room",
            "amenity_ids": amenity_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
