from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import (
    amenities,
    auth,
    bookings,
    locations,
    pricing_rules,
    recommendations,
    rooms,
    smart_booking,
    users,
)


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="REST API for coworking rooms, bookings, dynamic pricing and recommendations.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(locations.router)
app.include_router(amenities.router)
app.include_router(rooms.router)
app.include_router(pricing_rules.router)
app.include_router(bookings.router)
app.include_router(recommendations.router)
app.include_router(smart_booking.router)
