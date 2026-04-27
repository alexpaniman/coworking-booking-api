from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ROOM_TYPE_MEETING, ROOM_TYPE_WORKSPACE, Amenity, Room
from app.schemas import RecommendationOption, RecommendationRequest
from app.services.bookings import has_booking_conflict, is_within_working_hours
from app.services.pricing import calculate_dynamic_price


SLOT_STEP_MINUTES = 30
MAX_OPTIONS = 10


def room_has_amenities(room: Room, amenity_ids: set[int]) -> bool:
    if not amenity_ids:
        return True
    room_amenity_ids = {amenity.id for amenity in room.amenities}
    return amenity_ids.issubset(room_amenity_ids)


def load_candidate_rooms(db: Session, payload: RecommendationRequest) -> list[Room]:
    statement = (
        select(Room)
        .options(selectinload(Room.amenities))
        .where(Room.is_active.is_(True), Room.capacity >= payload.people_count)
        .order_by(Room.id)
    )
    if payload.location_id is not None:
        statement = statement.where(Room.location_id == payload.location_id)
    if payload.need_meeting_room:
        statement = statement.where(Room.room_type == ROOM_TYPE_MEETING)
    else:
        statement = statement.where(Room.room_type.in_([ROOM_TYPE_WORKSPACE, ROOM_TYPE_MEETING]))

    rooms = list(db.scalars(statement).all())
    return [room for room in rooms if room_has_amenities(room, set(payload.amenity_ids))]


def validate_requested_amenities(db: Session, amenity_ids: list[int]) -> None:
    if not amenity_ids:
        return
    unique_ids = set(amenity_ids)
    existing_count = len(db.scalars(select(Amenity).where(Amenity.id.in_(unique_ids))).all())
    if existing_count != len(unique_ids):
        raise ValueError("Unknown amenity id")


def calculate_score(room: Room, price: Decimal, start_at: datetime, payload: RecommendationRequest) -> float:
    score = 100.0
    score -= float(price) / 100.0
    score -= start_at.hour * 0.15
    score -= max(room.capacity - payload.people_count, 0) * 0.4
    if not payload.need_meeting_room and room.room_type == ROOM_TYPE_WORKSPACE:
        score += 5.0
    if payload.need_meeting_room and room.room_type == ROOM_TYPE_MEETING:
        score += 5.0
    return round(score, 2)


def build_recommendations(db: Session, payload: RecommendationRequest) -> list[RecommendationOption]:
    validate_requested_amenities(db, payload.amenity_ids)
    window_start = datetime.combine(payload.date, payload.earliest_start)
    window_end = datetime.combine(payload.date, payload.latest_end)
    duration = timedelta(minutes=payload.duration_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)

    options: list[RecommendationOption] = []
    for room in load_candidate_rooms(db, payload):
        slot_start = window_start
        while slot_start + duration <= window_end:
            slot_end = slot_start + duration
            if is_within_working_hours(room, slot_start, slot_end) and not has_booking_conflict(
                db,
                room.id,
                slot_start,
                slot_end,
                buffer_minutes=room.buffer_minutes,
            ):
                price = calculate_dynamic_price(db, room, slot_start, slot_end)
                if payload.max_price is None or price <= payload.max_price:
                    options.append(
                        RecommendationOption(
                            room_id=room.id,
                            room_name=room.name,
                            room_type=room.room_type,
                            location_id=room.location_id,
                            start_at=slot_start,
                            end_at=slot_end,
                            price=price,
                            score=calculate_score(room, price, slot_start, payload),
                        )
                    )
            slot_start += step

    options.sort(key=lambda option: (-option.score, option.price, option.start_at))
    return options[:MAX_OPTIONS]
