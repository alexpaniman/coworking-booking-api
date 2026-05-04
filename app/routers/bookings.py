from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.core.time import utc_now
from app.database import get_db
from app.models import (
    BOOKING_STATUS_CANCELLED,
    BOOKING_STATUS_CONFIRMED,
    USER_ROLE_ADMIN,
    Booking,
    Room,
    User,
)
from app.schemas import BookingCreate, BookingRead, BookingReschedule
from app.services.bookings import (
    MAX_BOOKING_MINUTES,
    MIN_BOOKING_MINUTES,
    has_booking_conflict,
    is_valid_booking_duration,
    is_within_working_hours,
)
from app.services.pricing import calculate_price_breakdown, serialize_price_breakdown
from app.services.telegram import notify_booking


router = APIRouter(prefix="/bookings", tags=["bookings"])


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def get_booking_or_404(db: Session, booking_id: int) -> Booking:
    statement = (
        select(Booking)
        .options(selectinload(Booking.room))
        .where(Booking.id == booking_id)
    )
    booking = db.scalar(statement)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


def ensure_booking_access(booking: Booking, current_user: User) -> None:
    if current_user.role != USER_ROLE_ADMIN and booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Booking access denied")


def validate_booking_slot(
    db: Session,
    room: Room,
    start_at: datetime,
    end_at: datetime,
    people_count: int,
    exclude_booking_id: int | None = None,
) -> None:
    if start_at >= end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_at must be later than start_at",
        )
    if start_at <= utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book a past slot")
    if not is_valid_booking_duration(start_at, end_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Booking duration must be between {MIN_BOOKING_MINUTES} "
                f"and {MAX_BOOKING_MINUTES} minutes"
            ),
        )
    if people_count > room.capacity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room capacity is too small")
    if not is_within_working_hours(room, start_at, end_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is outside location working hours",
        )
    if has_booking_conflict(
        db,
        room.id,
        start_at,
        end_at,
        exclude_booking_id=exclude_booking_id,
        buffer_minutes=room.buffer_minutes,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already booked for this time",
        )


@router.get("", response_model=list[BookingRead])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Booking]:
    statement = select(Booking).order_by(Booking.start_at)
    if current_user.role != USER_ROLE_ADMIN:
        statement = statement.where(Booking.user_id == current_user.id)
    return list(db.scalars(statement).all())


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    ensure_booking_access(booking, current_user)
    return booking


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    start_at = normalize_datetime(payload.start_at)
    end_at = normalize_datetime(payload.end_at)

    room = db.get(Room, payload.room_id)
    if room is None or not room.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    validate_booking_slot(db, room, start_at, end_at, payload.people_count)

    price_breakdown = calculate_price_breakdown(db, room, start_at, end_at)
    booking = Booking(
        user_id=current_user.id,
        room_id=room.id,
        start_at=start_at,
        end_at=end_at,
        people_count=payload.people_count,
        total_price=price_breakdown["final_price"],
        price_breakdown=serialize_price_breakdown(price_breakdown),
        status=BOOKING_STATUS_CONFIRMED,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    booking = get_booking_or_404(db, booking.id)
    notify_booking(booking, "created")
    return booking


@router.patch("/{booking_id}/reschedule", response_model=BookingRead)
def reschedule_booking(
    booking_id: int,
    payload: BookingReschedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    ensure_booking_access(booking, current_user)
    if booking.status == BOOKING_STATUS_CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule cancelled booking",
        )

    start_at = normalize_datetime(payload.start_at)
    end_at = normalize_datetime(payload.end_at)
    people_count = payload.people_count or booking.people_count
    room = booking.room
    validate_booking_slot(
        db,
        room,
        start_at,
        end_at,
        people_count,
        exclude_booking_id=booking.id,
    )

    booking.start_at = start_at
    booking.end_at = end_at
    booking.people_count = people_count
    price_breakdown = calculate_price_breakdown(db, room, start_at, end_at)
    booking.total_price = price_breakdown["final_price"]
    booking.price_breakdown = serialize_price_breakdown(price_breakdown)
    db.commit()
    db.refresh(booking)
    booking = get_booking_or_404(db, booking.id)
    notify_booking(booking, "rescheduled")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    ensure_booking_access(booking, current_user)
    if booking.status == BOOKING_STATUS_CANCELLED:
        return booking
    booking.status = BOOKING_STATUS_CANCELLED
    booking.cancelled_at = utc_now()
    db.commit()
    db.refresh(booking)
    booking = get_booking_or_404(db, booking.id)
    notify_booking(booking, "cancelled")
    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    cancel_booking(booking_id, db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
