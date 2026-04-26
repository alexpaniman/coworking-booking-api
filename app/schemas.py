from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import ROOM_TYPE_MEETING, ROOM_TYPE_WORKSPACE, USER_ROLE_ADMIN, USER_ROLE_USER


UserRole = Literal["admin", "user"]
RoomType = Literal["workspace", "meeting_room"]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = USER_ROLE_USER


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=5, max_length=255)
    timezone: str = Field(default="Europe/Moscow", max_length=64)
    is_active: bool = True


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=5, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class LocationRead(BaseModel):
    id: int
    name: str
    address: str
    timezone: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AmenityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None


class AmenityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None


class AmenityRead(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    location_id: int
    name: str = Field(min_length=2, max_length=150)
    room_type: RoomType = ROOM_TYPE_WORKSPACE
    capacity: int = Field(gt=0)
    base_price_per_hour: Decimal = Field(gt=0, decimal_places=2)
    description: str | None = None
    is_active: bool = True
    amenity_ids: list[int] = Field(default_factory=list)


class RoomUpdate(BaseModel):
    location_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    room_type: RoomType | None = None
    capacity: int | None = Field(default=None, gt=0)
    base_price_per_hour: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    description: str | None = None
    is_active: bool | None = None
    amenity_ids: list[int] | None = None


class RoomRead(BaseModel):
    id: int
    location_id: int
    name: str
    room_type: RoomType
    capacity: int
    base_price_per_hour: Decimal
    description: str | None
    is_active: bool
    amenities: list[AmenityRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PricingRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    multiplier: Decimal = Field(gt=0, decimal_places=2)
    priority: int = Field(default=100, ge=0)
    room_type: RoomType | None = None
    location_id: int | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_time_window(self) -> "PricingRuleCreate":
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValueError("end_time must be later than start_time")
        return self


class PricingRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    multiplier: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    priority: int | None = Field(default=None, ge=0)
    room_type: RoomType | None = None
    location_id: int | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "PricingRuleUpdate":
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValueError("end_time must be later than start_time")
        return self


class PricingRuleRead(BaseModel):
    id: int
    name: str
    multiplier: Decimal
    priority: int
    room_type: RoomType | None
    location_id: int | None
    weekday: int | None
    start_time: time | None
    end_time: time | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    room_id: int
    start_at: datetime
    end_at: datetime
    people_count: int = Field(gt=0)


class BookingRead(BaseModel):
    id: int
    user_id: int
    room_id: int
    start_at: datetime
    end_at: datetime
    people_count: int
    total_price: Decimal
    status: str
    created_at: datetime
    cancelled_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RecommendationRequest(BaseModel):
    date: date
    earliest_start: time
    latest_end: time
    duration_minutes: int = Field(ge=30, le=8 * 60)
    people_count: int = Field(gt=0)
    need_meeting_room: bool = False
    location_id: int | None = None
    max_price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    amenity_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_request_window(self) -> "RecommendationRequest":
        if self.earliest_start >= self.latest_end:
            raise ValueError("latest_end must be later than earliest_start")
        return self


class RecommendationOption(BaseModel):
    room_id: int
    room_name: str
    room_type: RoomType
    location_id: int
    start_at: datetime
    end_at: datetime
    price: Decimal
    score: float


class RecommendationResponse(BaseModel):
    options: list[RecommendationOption]


VALID_USER_ROLES = {USER_ROLE_ADMIN, USER_ROLE_USER}
VALID_ROOM_TYPES = {ROOM_TYPE_WORKSPACE, ROOM_TYPE_MEETING}
