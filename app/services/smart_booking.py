import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas import (
    RecommendationOption,
    SmartBookingPeriod,
    SmartBookingRequest,
    SmartBookingRoomOption,
)
from app.services.recommendations import generate_recommendation_options


QUOTE_TTL_MINUTES = 5


def encode_part(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode_part(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_payload(payload: bytes) -> str:
    settings = get_settings()
    signature = hmac.new(str(settings.secret_key).encode("utf-8"), payload, hashlib.sha256).digest()
    return encode_part(signature)


def create_option_token(option: RecommendationOption, people_count: int, expires_at: datetime) -> str:
    price_breakdown = {
        key: str(value) for key, value in option.price_breakdown.model_dump().items()
    }
    payload = json.dumps(
        {
            "room_id": option.room_id,
            "start_at": option.start_at.isoformat(),
            "end_at": option.end_at.isoformat(),
            "people_count": people_count,
            "quoted_price": str(option.price),
            "price_breakdown": price_breakdown,
            "expires_at": expires_at.isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{encode_part(payload)}.{sign_payload(payload)}"


def decode_option_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", 1)
        payload = decode_part(payload_part)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid smart booking option token") from exc
    expected_signature = sign_payload(payload)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise ValueError("Invalid smart booking option token")

    try:
        decoded = json.loads(payload)
        return {
            "room_id": int(decoded["room_id"]),
            "start_at": datetime.fromisoformat(decoded["start_at"]),
            "end_at": datetime.fromisoformat(decoded["end_at"]),
            "people_count": int(decoded["people_count"]),
            "quoted_price": Decimal(str(decoded["quoted_price"])),
            "price_breakdown": decoded["price_breakdown"],
            "expires_at": datetime.fromisoformat(decoded["expires_at"]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid smart booking option token") from exc


def ensure_quote_is_active(option: dict) -> None:
    if datetime.utcnow() > option["expires_at"]:
        raise ValueError("Smart booking quote expired")


def option_with_token(
    option: RecommendationOption,
    people_count: int,
    expires_at: datetime,
) -> SmartBookingRoomOption:
    return SmartBookingRoomOption(
        **option.model_dump(),
        option_token=create_option_token(option, people_count, expires_at),
        quote_expires_at=expires_at,
    )


def group_options_by_period(
    options: list[RecommendationOption],
    people_count: int,
) -> list[SmartBookingPeriod]:
    expires_at = datetime.utcnow() + timedelta(minutes=QUOTE_TTL_MINUTES)
    periods: dict[tuple[datetime, datetime], list[SmartBookingRoomOption]] = {}
    for option in options:
        key = (option.start_at, option.end_at)
        periods.setdefault(key, []).append(option_with_token(option, people_count, expires_at))

    response_periods: list[SmartBookingPeriod] = []
    for (start_at, end_at), room_options in periods.items():
        room_options.sort(key=lambda option: (option.price, -option.score, option.room_id))
        response_periods.append(
            SmartBookingPeriod(
                start_at=start_at,
                end_at=end_at,
                cheapest_price=min(Decimal(str(option.price)) for option in room_options),
                options=room_options,
            )
        )

    response_periods.sort(key=lambda period: (period.start_at, period.cheapest_price))
    return response_periods


def build_smart_booking_periods(db: Session, payload: SmartBookingRequest) -> list[SmartBookingPeriod]:
    options = generate_recommendation_options(db, payload)
    return group_options_by_period(options, payload.people_count)
