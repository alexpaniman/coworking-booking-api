from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BOOKING_STATUS_CONFIRMED, Booking, Room


def has_booking_conflict(
    db: Session,
    room_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_booking_id: int | None = None,
    buffer_minutes: int = 0,
) -> bool:
    buffer_delta = timedelta(minutes=buffer_minutes)
    protected_start = start_at - buffer_delta
    protected_end = end_at + buffer_delta
    statement = select(Booking).where(
        Booking.room_id == room_id,
        Booking.status == BOOKING_STATUS_CONFIRMED,
        Booking.start_at < protected_end,
        Booking.end_at > protected_start,
    )
    if exclude_booking_id is not None:
        statement = statement.where(Booking.id != exclude_booking_id)
    return db.scalar(statement) is not None


def is_within_working_hours(room: Room, start_at: datetime, end_at: datetime) -> bool:
    return room.location.opens_at <= start_at.time() and end_at.time() <= room.location.closes_at
