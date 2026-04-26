import logging
from datetime import datetime

import httpx

from app.core.config import get_settings
from app.models import Booking


logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send_message(self, text: str) -> bool:
        if not self.settings.telegram_enabled:
            return False
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            logger.warning("Telegram is enabled but token or chat id is missing")
            return False

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self.settings.telegram_chat_id, "text": text}
        try:
            response = httpx.post(url, json=payload, timeout=5)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Telegram notification failed: %s", exc)
            return False
        return True


def format_booking_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def build_booking_message(booking: Booking, action: str) -> str:
    room_name = booking.room.name if booking.room else f"room #{booking.room_id}"
    return (
        f"Booking {action}\n"
        f"Room: {room_name}\n"
        f"Time: {format_booking_time(booking.start_at)} - {format_booking_time(booking.end_at)}\n"
        f"People: {booking.people_count}\n"
        f"Price: {booking.total_price} RUB"
    )


def notify_booking(booking: Booking, action: str) -> bool:
    return TelegramNotifier().send_message(build_booking_message(booking, action))
