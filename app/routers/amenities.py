from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Amenity, User
from app.schemas import AmenityCreate, AmenityRead, AmenityUpdate


router = APIRouter(prefix="/amenities", tags=["amenities"])


@router.get("", response_model=list[AmenityRead])
def list_amenities(db: Session = Depends(get_db)) -> list[Amenity]:
    return list(db.scalars(select(Amenity).order_by(Amenity.id)).all())


@router.get("/{amenity_id}", response_model=AmenityRead)
def get_amenity(amenity_id: int, db: Session = Depends(get_db)) -> Amenity:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amenity not found")
    return amenity


@router.post("", response_model=AmenityRead, status_code=status.HTTP_201_CREATED)
def create_amenity(
    payload: AmenityCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Amenity:
    amenity = Amenity(**payload.model_dump())
    db.add(amenity)
    db.commit()
    db.refresh(amenity)
    return amenity


@router.patch("/{amenity_id}", response_model=AmenityRead)
def update_amenity(
    amenity_id: int,
    payload: AmenityUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Amenity:
    amenity = get_amenity(amenity_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(amenity, field, value)
    db.commit()
    db.refresh(amenity)
    return amenity


@router.delete("/{amenity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_amenity(
    amenity_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    amenity = get_amenity(amenity_id, db)
    db.delete(amenity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

