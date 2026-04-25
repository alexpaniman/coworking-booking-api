from fastapi import FastAPI

from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="REST API for coworking rooms, bookings, dynamic pricing and recommendations.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}

