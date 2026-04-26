from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.database import get_db
from app.models import Amenity, Location, Room, User
from app.schemas import RoomCreate, RoomRead, RoomUpdate, VALID_ROOM_TYPES


router = APIRouter(prefix="/rooms", tags=["rooms"])


def load_amenities(db: Session, amenity_ids: list[int]) -> list[Amenity]:
    if not amenity_ids:
        return []
    unique_ids = set(amenity_ids)
    amenities = list(db.scalars(select(Amenity).where(Amenity.id.in_(unique_ids))).all())
    if len(amenities) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown amenity id")
    return amenities


def validate_room_payload(db: Session, payload: RoomCreate | RoomUpdate) -> None:
    if payload.location_id is not None and db.get(Location, payload.location_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown location id")
    if payload.room_type is not None and payload.room_type not in VALID_ROOM_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown room type")


@router.get("", response_model=list[RoomRead])
def list_rooms(db: Session = Depends(get_db)) -> list[Room]:
    statement = select(Room).options(selectinload(Room.amenities)).order_by(Room.id)
    return list(db.scalars(statement).all())


@router.get("/{room_id}", response_model=RoomRead)
def get_room(room_id: int, db: Session = Depends(get_db)) -> Room:
    statement = select(Room).options(selectinload(Room.amenities)).where(Room.id == room_id)
    room = db.scalar(statement)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Room:
    validate_room_payload(db, payload)
    amenities = load_amenities(db, payload.amenity_ids)
    room_data = payload.model_dump(exclude={"amenity_ids"})
    room = Room(**room_data)
    room.amenities = amenities
    db.add(room)
    db.commit()
    db.refresh(room)
    return get_room(room.id, db)


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Room:
    room = get_room(room_id, db)
    validate_room_payload(db, payload)
    data = payload.model_dump(exclude_unset=True, exclude={"amenity_ids"})
    for field, value in data.items():
        setattr(room, field, value)
    if payload.amenity_ids is not None:
        room.amenities = load_amenities(db, payload.amenity_ids)
    db.commit()
    db.refresh(room)
    return get_room(room.id, db)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    room = get_room(room_id, db)
    room.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
