from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BOOKING_STATUS_CONFIRMED, Booking


def has_booking_conflict(
    db: Session,
    room_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_booking_id: int | None = None,
) -> bool:
    statement = select(Booking).where(
        Booking.room_id == room_id,
        Booking.status == BOOKING_STATUS_CONFIRMED,
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )
    if exclude_booking_id is not None:
        statement = statement.where(Booking.id != exclude_booking_id)
    return db.scalar(statement) is not None

