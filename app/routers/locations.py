from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Location, User
from app.schemas import LocationCreate, LocationRead, LocationUpdate


router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)) -> list[Location]:
    return list(db.scalars(select(Location).order_by(Location.id)).all())


@router.get("/{location_id}", response_model=LocationRead)
def get_location(location_id: int, db: Session = Depends(get_db)) -> Location:
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Location:
    location = Location(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.patch("/{location_id}", response_model=LocationRead)
def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Location:
    location = get_location(location_id, db)
    data = payload.model_dump(exclude_unset=True)
    opens_at = data.get("opens_at", location.opens_at)
    closes_at = data.get("closes_at", location.closes_at)
    if opens_at >= closes_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="closes_at must be later than opens_at",
        )
    for field, value in data.items():
        setattr(location, field, value)
    db.commit()
    db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    location = get_location(location_id, db)
    location.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
