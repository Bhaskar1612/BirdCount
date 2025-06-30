from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends, Request
from typing import List
from Common.shared_utils import MODEL_TYPE_OBJECT_DETECTION, MODEL_TYPE_BIRD_COUNT, get_model
from Common.api.auth import get_current_user
from BirdCount.api.upload import upload_images_bird_count, upload_folders_bird_count
from ObjectDetection.api.upload import upload_images_object_detection, upload_folders_object_detection

router = APIRouter()

@router.post("/upload")
async def upload_router(
    request: Request,
    type: str = Form(...), 
    task: str = Form(...), 
    consent: bool = Form(...), 
    file: UploadFile = File(...),
    current_user: int = Depends(get_current_user),
):
    user_id = current_user
    if task == "object-detection":
        model_type = MODEL_TYPE_OBJECT_DETECTION
    elif task == "bird-count":
        model_type = MODEL_TYPE_BIRD_COUNT
    else:
        raise HTTPException(status_code=400, detail="Invalid task")

    if type == "image":
        return await upload_images_common(
            request, 
            model_type=model_type, 
            files=[file], 
            consent=consent,
            user_id = user_id
        )
    elif type == "folder":
        return await upload_folder_common(
            request, 
            model_type=model_type, 
            folders=[file], 
            consent=consent,
            user_id = user_id
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid type")
    
async def upload_images_common(
    request: Request, 
    model_type: int, 
    files: List[UploadFile] = File(...), 
    consent: bool = Form(...),
    model = Depends(get_model),
    user_id: int = Depends(get_current_user)
):
    if model_type == MODEL_TYPE_OBJECT_DETECTION:
        return await upload_images_object_detection(request, files=files, model=model, user_id=user_id, consent=consent)
    elif model_type == MODEL_TYPE_BIRD_COUNT:
        return await upload_images_bird_count(request, files=files, model=model, user_id=user_id, consent=consent)
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")
    
async def upload_folder_common(
    request: Request, 
    model_type: int, 
    folders: List[UploadFile] = File(...), 
    consent: bool = Form(...),
    model = Depends(get_model),
    user_id: int = Depends(get_current_user)
):
    if model_type == MODEL_TYPE_OBJECT_DETECTION:
        return await upload_folders_object_detection(request, folders=folders, model=model, user_id=user_id, consent=consent)
    elif model_type == MODEL_TYPE_BIRD_COUNT:
        return await upload_folders_bird_count(request, folders=folders, model=model, user_id=user_id, consent=consent)
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")