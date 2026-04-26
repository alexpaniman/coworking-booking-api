from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"

ROOM_TYPE_WORKSPACE = "workspace"
ROOM_TYPE_MEETING = "meeting_room"

BOOKING_STATUS_CONFIRMED = "confirmed"
BOOKING_STATUS_CANCELLED = "cancelled"


room_amenities = Table(
    "room_amenities",
    Base.metadata,
    Column("room_id", ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    Column("amenity_id", ForeignKey("amenities.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default=USER_ROLE_USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="location")
    pricing_rules: Mapped[list["PricingRule"]] = relationship("PricingRule", back_populates="location")


class Amenity(Base):
    __tablename__ = "amenities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    rooms: Mapped[list["Room"]] = relationship(
        "Room",
        secondary=room_amenities,
        back_populates="amenities",
    )


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("location_id", "name", name="uq_room_location_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    room_type: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    base_price_per_hour: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped[Location] = relationship("Location", back_populates="rooms")
    amenities: Mapped[list[Amenity]] = relationship(
        "Amenity",
        secondary=room_amenities,
        back_populates="rooms",
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="room")


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time = mapped_column(Time, nullable=True)
    end_time = mapped_column(Time, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped[Location | None] = relationship("Location", back_populates="pricing_rules")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    people_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=BOOKING_STATUS_CONFIRMED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="bookings")
    room: Mapped[Room] = relationship("Room", back_populates="bookings")
