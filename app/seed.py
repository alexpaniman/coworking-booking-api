from datetime import time
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import Amenity, Location, PricingRule, Room, User


def get_or_create_user(db, email: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=hash_password("secret123"),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def seed() -> None:
    db = SessionLocal()
    try:
        get_or_create_user(db, "admin@example.com", "admin")
        get_or_create_user(db, "user@example.com", "user")

        location = db.scalar(select(Location).where(Location.name == "Center Hub"))
        if location is None:
            location = Location(name="Center Hub", address="Main street 1")
            db.add(location)
            db.flush()

        whiteboard = db.scalar(select(Amenity).where(Amenity.name == "Whiteboard"))
        if whiteboard is None:
            whiteboard = Amenity(name="Whiteboard", description="Wall-mounted board")
            db.add(whiteboard)
            db.flush()

        projector = db.scalar(select(Amenity).where(Amenity.name == "Projector"))
        if projector is None:
            projector = Amenity(name="Projector", description="Meeting room projector")
            db.add(projector)
            db.flush()

        if db.scalar(select(Room).where(Room.name == "Open Space A")) is None:
            room = Room(
                location_id=location.id,
                name="Open Space A",
                room_type="workspace",
                capacity=8,
                base_price_per_hour=Decimal("500.00"),
                description="Shared workspace for small teams",
            )
            room.amenities = [whiteboard]
            db.add(room)

        if db.scalar(select(Room).where(Room.name == "Focus Room")) is None:
            room = Room(
                location_id=location.id,
                name="Focus Room",
                room_type="meeting_room",
                capacity=6,
                base_price_per_hour=Decimal("900.00"),
                description="Quiet meeting room",
            )
            room.amenities = [whiteboard, projector]
            db.add(room)

        if db.scalar(select(PricingRule).where(PricingRule.name == "Workday peak")) is None:
            db.add(
                PricingRule(
                    name="Workday peak",
                    multiplier=Decimal("1.40"),
                    priority=300,
                    start_time=time(hour=10),
                    end_time=time(hour=18),
                    is_active=True,
                )
            )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
