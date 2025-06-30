from fastapi import APIRouter, Request, HTTPException, Query, Depends
from typing import Optional

from Common.shared_utils import logger
from ObjectDetection.api.active_learning import get_active_learning_images
from BirdCount.api.images import get_images_birdcount
from ObjectDetection.api.images import get_images as od_get_images
from BirdCount.api.active_learning import get_active_learning_images_birdcount
from Common.api.auth import get_current_user

router = APIRouter()

@router.get("/images")
async def get_images(
    request: Request,
    task: str = Query(..., description="Task type: 'object-detection' or 'bird-count'"),
    image_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    box_count_filter: Optional[str] = Query(None),
    query: Optional[str] = Query(None, description="Text query for CLIP search"),
    page: str = Query("1", description="Page number or 'active-learning' for active learning mode"),
    limit: Optional[int] = Query(None, description="Active learning limit; must be one of 5,10,20"),
    page_size: int = Query(10, ge=1, le=100, description="Page size for object-detection"),
    user_id: int = Depends(get_current_user),
):
    # Active Learning mode
    if page.lower() == "active-learning":
        if task.lower() != "object-detection":
            raise HTTPException(status_code=400, detail="Active-learning only valid for object-detection")
        if limit not in (5, 10, 20):
            raise HTTPException(status_code=400, detail="Limit must be one of 5, 10, or 20")
        return await get_active_learning_images(request, limit=limit, user_id=user_id)

    if page and page.lower() == "active-learning-birdcount":
        if limit is None:
            raise HTTPException(status_code=400, detail="Limit parameter required when page is active-learning-bird-count")
        if limit not in [5, 10, 20]:
            raise HTTPException(status_code=400, detail="Limit must be 5, 10, or 20")
        return await get_active_learning_images_birdcount(request, limit=limit, user_id=user_id)

    # Numeric page for object-detection or bird-count
    try:
        page_int = int(page)
    except ValueError:
        raise HTTPException(status_code=400, detail="Page must be an integer or 'active-learning'")
    if page_int < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")

    if task.lower() == "object-detection":
        return await od_get_images(
            request=request,
            user_id=user_id,
            image_id=image_id,
            class_id=class_id,
            box_count_filter=box_count_filter,
            query=query,
            page=page_int,
            page_size=page_size,
        )
    elif task.lower() == "bird-count":
        return await get_images_birdcount(request, user_id=user_id, image_id=image_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid task")
