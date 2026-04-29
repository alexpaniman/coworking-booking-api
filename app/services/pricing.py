from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BOOKING_STATUS_CONFIRMED, Booking, PricingRule, Room


MEETING_ROOM_MULTIPLIER = Decimal("1.20")
WORKSPACE_MULTIPLIER = Decimal("1.00")
MAX_OCCUPANCY_SURCHARGE = Decimal("0.30")


def to_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_from(value: object) -> Decimal:
    return Decimal(str(value))


def duration_hours(start_at: datetime, end_at: datetime) -> Decimal:
    seconds = Decimal(str((end_at - start_at).total_seconds()))
    return seconds / Decimal("3600")


def time_windows_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and end_a > start_b


def room_type_multiplier(room: Room) -> Decimal:
    if room.room_type == "meeting_room":
        return MEETING_ROOM_MULTIPLIER
    return WORKSPACE_MULTIPLIER


def get_occupancy_multiplier(db: Session, room: Room, start_at: datetime) -> Decimal:
    day_start = start_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = start_at.replace(hour=23, minute=59, second=59, microsecond=999999)
    booking_count = db.scalar(
        select(func.count(Booking.id)).where(
            Booking.room_id == room.id,
            Booking.status == BOOKING_STATUS_CONFIRMED,
            Booking.start_at >= day_start,
            Booking.start_at <= day_end,
        )
    )
    ratio = min(Decimal(str(booking_count or 0)) / Decimal("8"), Decimal("1"))
    return Decimal("1.00") + ratio * MAX_OCCUPANCY_SURCHARGE


def rule_matches(rule: PricingRule, room: Room, start_at: datetime, end_at: datetime) -> bool:
    if not rule.is_active:
        return False
    if rule.room_type and rule.room_type != room.room_type:
        return False
    if rule.location_id and rule.location_id != room.location_id:
        return False
    if rule.weekday is not None and rule.weekday != start_at.weekday():
        return False
    if rule.start_time and rule.end_time:
        return time_windows_overlap(rule.start_time, rule.end_time, start_at.time(), end_at.time())
    return True


def get_pricing_rule_multiplier(db: Session, room: Room, start_at: datetime, end_at: datetime) -> Decimal:
    rules = db.scalars(select(PricingRule).where(PricingRule.is_active.is_(True))).all()
    matching_rules = [rule for rule in rules if rule_matches(rule, room, start_at, end_at)]
    if not matching_rules:
        return Decimal("1.00")
    matching_rules.sort(key=lambda rule: (rule.priority, decimal_from(rule.multiplier)), reverse=True)
    return decimal_from(matching_rules[0].multiplier)


def calculate_dynamic_price(db: Session, room: Room, start_at: datetime, end_at: datetime) -> Decimal:
    return calculate_price_breakdown(db, room, start_at, end_at)["final_price"]


def calculate_price_breakdown(
    db: Session,
    room: Room,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, Decimal]:
    hours = duration_hours(start_at, end_at)
    base_price = decimal_from(room.base_price_per_hour) * hours
    type_multiplier = room_type_multiplier(room)
    rule_multiplier = get_pricing_rule_multiplier(db, room, start_at, end_at)
    occupancy_multiplier = get_occupancy_multiplier(db, room, start_at)
    final_price = base_price * type_multiplier * rule_multiplier * occupancy_multiplier
    return {
        "base_price": to_money(base_price),
        "duration_hours": hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "room_type_multiplier": type_multiplier,
        "pricing_rule_multiplier": rule_multiplier,
        "occupancy_multiplier": occupancy_multiplier.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "final_price": to_money(final_price),
    }


def serialize_price_breakdown(breakdown: dict[str, Decimal]) -> dict[str, str]:
    return {key: str(value) for key, value in breakdown.items()}
