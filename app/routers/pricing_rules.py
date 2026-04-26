from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Location, PricingRule, User
from app.schemas import PricingRuleCreate, PricingRuleRead, PricingRuleUpdate, VALID_ROOM_TYPES


router = APIRouter(prefix="/pricing-rules", tags=["pricing-rules"])


def validate_pricing_rule(db: Session, payload: PricingRuleCreate | PricingRuleUpdate) -> None:
    if payload.location_id is not None and db.get(Location, payload.location_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown location id")
    if payload.room_type is not None and payload.room_type not in VALID_ROOM_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown room type")


@router.get("", response_model=list[PricingRuleRead])
def list_pricing_rules(db: Session = Depends(get_db)) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.id)).all())


@router.get("/{rule_id}", response_model=PricingRuleRead)
def get_pricing_rule(rule_id: int, db: Session = Depends(get_db)) -> PricingRule:
    rule = db.get(PricingRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing rule not found")
    return rule


@router.post("", response_model=PricingRuleRead, status_code=status.HTTP_201_CREATED)
def create_pricing_rule(
    payload: PricingRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PricingRule:
    validate_pricing_rule(db, payload)
    rule = PricingRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}", response_model=PricingRuleRead)
def update_pricing_rule(
    rule_id: int,
    payload: PricingRuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PricingRule:
    rule = get_pricing_rule(rule_id, db)
    validate_pricing_rule(db, payload)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pricing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    rule = get_pricing_rule(rule_id, db)
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
