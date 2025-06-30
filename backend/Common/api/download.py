from fastapi import APIRouter, Request, HTTPException, Depends
from ObjectDetection.api.download import download_object_detection_images
from Common.api.auth import get_current_user

router = APIRouter()

@router.get("/download")
async def download_images(
    request: Request, 
    task: str, 
    # user_id: int = Depends(get_user_id)
    user_id: int = Depends(get_current_user),
):
    if task == "object-detection":
        return await download_object_detection_images(request, user_id=user_id)
    elif task == "bird-count":
        raise HTTPException(status_code=400, detail="Download not supported for task 'bird-count'")
    else:
        raise HTTPException(status_code=400, detail="Invalid task")