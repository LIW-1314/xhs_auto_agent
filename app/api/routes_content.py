from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    ContentReviewRequest,
    ContentReviewResponse,
)
from app.services.content_service import generate_contents
from app.services.review_service import review_content

router = APIRouter(prefix="/content", tags=["Content"])


@router.post("/generate", response_model=ContentGenerateResponse)
def generate_content_endpoint(request: ContentGenerateRequest):
    try:
        return generate_contents(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review", response_model=ContentReviewResponse)
def review_content_endpoint(request: ContentReviewRequest):
    try:
        return ContentReviewResponse(review=review_content(request.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
