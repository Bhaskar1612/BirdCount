import os
import uuid
import time
import asyncio
import shutil
import tarfile
import rarfile
from typing import List
from fastapi import Request, HTTPException, File, UploadFile, Depends, Form
from fastapi.responses import StreamingResponse
from PIL import Image
import torch
import numpy as np

from Common.shared_utils import logger, get_model, UPLOAD_DIR, get_db_connection, MODEL_TYPE_OBJECT_DETECTION
from Common.api.auth import get_current_user

from ObjectDetection.inference.inference import run_inference

MAX_FILE_SIZE = 1 * 1024**3  # 1 GB

async def upload_folders_object_detection(
    request: Request,
    folders: List[UploadFile] = File(...), 
    model = Depends(get_model),
    user_id: int = Depends(get_current_user),
    consent: bool = Form(...),
):
    uploaded_image_ids = []
    for folder in folders:
        if not any(folder.filename.lower().endswith(ext) for ext in ('.zip', '.rar', '.tar', '.gz', '.bz2', '.7z')):
            raise HTTPException(status_code=400, detail="Only ZIP, RAR, TAR, GZ, BZ2, and 7Z files are allowed")

        content = await folder.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds the 1GB size limit")

        ext = os.path.splitext(folder.filename)[1]
        temp_archive = os.path.join(UPLOAD_DIR, f"temp_{int(time.time())}{ext}")
        with open(temp_archive, "wb") as f:
            f.write(content)

        extract_dir = temp_archive + "_extract"
        os.makedirs(extract_dir, exist_ok=True)
        fname = folder.filename.lower()
        if fname.endswith(('.zip','.tar','.tar.gz','.tgz','.tar.bz2','.tbz','.tar.xz','.txz')):
            try:
                shutil.unpack_archive(temp_archive, extract_dir)
            except Exception:
                with tarfile.open(temp_archive) as tf:
                    tf.extractall(extract_dir)
        elif fname.endswith('.rar') and rarfile:
            with rarfile.RarFile(temp_archive) as rf:
                rf.extractall(extract_dir)
        else:
            os.remove(temp_archive)
            raise HTTPException(status_code=400, detail=f"Unsupported archive format: {folder.filename}")

        image_files = []
        for root, _, files in os.walk(extract_dir):
            if "__MACOSX" in root:
                continue
            for fn in files:
                if fn.startswith("._") or fn == ".DS_Store":
                    continue
                if fn.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_files.append(os.path.join(root, fn))
        total_images = len(image_files)

        async def event_stream():
            try:
                processed = 0
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM classes WHERE name = 'blan_blan'")
                        blan = cur.fetchone()
                        blan_id = blan[0] if blan else None
                        for path in image_files:
                            original = os.path.basename(path)
                            unique = f"{uuid.uuid4()}_{original}"
                            dst = os.path.join(UPLOAD_DIR, unique)
                            shutil.copy(path, dst)
                            img = Image.open(dst)
                            width, height = img.size
                            cur.execute(
                                """
                                INSERT INTO images (filename, filepath, width, height, user_id, model_type, consent)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (unique, dst, width, height, user_id, MODEL_TYPE_OBJECT_DETECTION, consent)
                            )
                            image_id = cur.fetchone()[0]
                            uploaded_image_ids.append(image_id)
                            
                            try:
                                if hasattr(model, 'predict'):
                                    detections = run_inference(image_path=dst, model=model)
                                else:
                                    actual_model = request.app.state.model
                                    detections = run_inference(image_path=dst, model=actual_model)
                                
                                if not detections and blan_id is not None:
                                    cur.execute(
                                        """
                                        INSERT INTO model_predicted_boxes (image_id, class_id, x, y, width, height, confidence)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            image_id,
                                            blan_id,
                                            0,
                                            0,
                                            0,
                                            0,
                                            1.0
                                        )
                                    )
                                else:
                                    for box in detections:
                                        cur.execute(
                                            """
                                            INSERT INTO model_predicted_boxes (image_id, class_id, x, y, width, height, confidence)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                                            """,
                                            (
                                                image_id,
                                                box['class_id'],
                                                box['x'],
                                                box['y'],
                                                box['width'],
                                                box['height'],
                                                box['confidence']
                                            )
                                        )
                    
                            except Exception as infer_err:
                                logger.error(f"Inference error for image {image_id}: {infer_err}")
                            
                            proc = request.app.state.clip_processor
                            clip_model = request.app.state.clip_model
                            img_clip = Image.open(dst)
                            inputs = proc(images=img_clip, return_tensors="pt", padding=True).to(clip_model.device)
                            with torch.no_grad():
                                emb = clip_model.get_image_features(**inputs).cpu().numpy()[0]
                            norm = np.linalg.norm(emb)
                            if norm > 0:
                                emb = emb / norm
                            cur.execute(
                                "INSERT INTO image_embeddings (image_id, embedding) VALUES (%s, %s)",
                                (image_id, emb.tolist())
                            )
                            
                            processed += 1
                            conn.commit()
                            progress = int((processed / total_images) * 100)
                            yield f'data: {{"progress": {progress}}}\n\n'
                            await asyncio.sleep(0.1)
                    yield f'data: {{"message": "Folders uploaded successfully", "uploaded_image_ids": {uploaded_image_ids}}}\n\n'
            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
                os.remove(temp_archive)
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
    return {
        "message": "Folders uploaded successfully",
        "uploaded_image_ids": uploaded_image_ids
    }
    
async def upload_images_object_detection(
    request: Request,
    files: List[UploadFile] = File(...),
    model = Depends(get_model),
    user_id: int = Depends(get_current_user),
    consent: bool = Form(...),
):
    logger.debug(f"Received upload request with consent: {consent}")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM classes WHERE name = 'blan_blan'")
                blan_blan_class = cur.fetchone()
                blan_blan_id = blan_blan_class[0] if blan_blan_class else None
                
                uploaded_ids = []
                for file in files:
                    unique_filename = f"{uuid.uuid4()}_{file.filename}"
                    file_path = os.path.join(UPLOAD_DIR, unique_filename)
                    
                    with open(file_path, "wb") as buffer:
                        content = await file.read()
                        buffer.write(content)
                    
                    img = Image.open(file_path)
                    width, height = img.size
                    
                    cur.execute(
                        """
                        INSERT INTO images (filename, filepath, width, height, user_id, model_type, consent) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s) 
                        RETURNING id
                        """,
                        (unique_filename, file_path, width, height, user_id, MODEL_TYPE_OBJECT_DETECTION, consent)
                    )
                    image_id = cur.fetchone()[0]
                    uploaded_ids.append(image_id)
                    
                    try:
                        if hasattr(model, 'predict'):
                            detections = run_inference(image_path=file_path, model=model)
                        else:
                            actual_model = request.app.state.model
                            detections = run_inference(image_path=file_path, model=actual_model)
                        
                        if not detections and blan_blan_id is not None:
                            cur.execute(
                                """
                                INSERT INTO model_predicted_boxes (image_id, class_id, x, y, width, height, confidence) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    image_id,
                                    blan_blan_id,
                                    0,
                                    0,
                                    0,
                                    0,
                                    1.0
                                )
                            )
                        else:
                            for box in detections:
                                cur.execute(
                                    """
                                    INSERT INTO model_predicted_boxes (image_id, class_id, x, y, width, height, confidence) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        image_id,
                                        box['class_id'],
                                        box['x'],
                                        box['y'],
                                        box['width'],
                                        box['height'],
                                        box['confidence']
                                    )
                                )
                        
                        proc = request.app.state.clip_processor
                        clip_model = request.app.state.clip_model
                        img_clip = Image.open(file_path)
                        inputs = proc(images=img_clip, return_tensors="pt", padding=True).to(clip_model.device)
                        with torch.no_grad():
                            emb = clip_model.get_image_features(**inputs).cpu().numpy()[0]
                        norm = np.linalg.norm(emb)
                        if norm > 0:
                            emb = emb / norm
                        cur.execute(
                            "INSERT INTO image_embeddings (image_id, embedding) VALUES (%s, %s)",
                            (image_id, emb.tolist())
                        )
                    except Exception as infer_err:
                        logger.error(f"Inference error for image {image_id}: {infer_err}")
                        
                conn.commit()
                return {"uploaded_image_ids": uploaded_ids, "user_id": user_id}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"error": str(e)}