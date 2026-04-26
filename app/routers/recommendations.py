from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import RecommendationRequest, RecommendationResponse
from app.services.recommendations import build_recommendations


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/booking-options", response_model=RecommendationResponse)
def recommend_booking_options(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RecommendationResponse:
    try:
        options = build_recommendations(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RecommendationResponse(options=options)

