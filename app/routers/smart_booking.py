from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import BOOKING_STATUS_CONFIRMED, Booking, Room, User
from app.routers.bookings import get_booking_or_404, validate_booking_slot
from app.schemas import BookingRead, SmartBookingConfirm, SmartBookingRequest, SmartBookingResponse
from app.services.pricing import calculate_price_breakdown, serialize_price_breakdown
from app.services.smart_booking import build_smart_booking_periods, decode_option_token
from app.services.telegram import notify_booking


router = APIRouter(prefix="/smart-booking", tags=["smart-booking"])


@router.post("/options", response_model=SmartBookingResponse)
def search_smart_booking_options(
    payload: SmartBookingRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SmartBookingResponse:
    try:
        periods = build_smart_booking_periods(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SmartBookingResponse(periods=periods)


@router.post("/book", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def book_smart_option(
    payload: SmartBookingConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    try:
        option = decode_option_token(payload.option_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    room = db.get(Room, option["room_id"])
    if room is None or not room.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    validate_booking_slot(
        db,
        room,
        option["start_at"],
        option["end_at"],
        option["people_count"],
    )
    price_breakdown = calculate_price_breakdown(db, room, option["start_at"], option["end_at"])
    booking = Booking(
        user_id=current_user.id,
        room_id=room.id,
        start_at=option["start_at"],
        end_at=option["end_at"],
        people_count=option["people_count"],
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
