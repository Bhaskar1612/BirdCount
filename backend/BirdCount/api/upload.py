import json
import os
import uuid
import time
from zipfile import ZipFile
from typing import List
from fastapi import HTTPException, File, UploadFile, Form, Request, Depends
from PIL import Image

from Common.shared_utils import logger, UPLOAD_DIR, get_db_connection, get_model, MODEL_TYPE_BIRD_COUNT
from Common.api.auth import get_current_user

import BirdCount.model_files.demomodified as demo

MAX_FILE_SIZE = 1 * 1024**3  # 1 GB

async def upload_folders_bird_count(
    request: Request,
    folders: List[UploadFile] = File(...),
    model = Depends(get_model), 
    user_id: int = Depends(get_current_user),      
    consent: bool = Form(False),
):
    uploaded_image_ids = []
    for folder in folders:
        if not any(folder.filename.lower().endswith(ext) for ext in ('.zip', '.rar', '.tar', '.gz', '.bz2', '.7z')):
            raise HTTPException(status_code=400, detail="Only ZIP, RAR, TAR, GZ, BZ2, and 7Z files are allowed")

        content = await folder.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds the 1GB size limit")

        temp_zip_path = os.path.join(UPLOAD_DIR, f"temp_{int(time.time())}.zip")
        try:
            with open(temp_zip_path, "wb") as buffer:
                buffer.write(content)

            with ZipFile(temp_zip_path) as zip_ref:
                total_uncompressed = sum(info.file_size for info in zip_ref.infolist())
                if total_uncompressed > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="Uncompressed content exceeds the 1GB limit")

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    with ZipFile(temp_zip_path) as zip_ref:
                        for file_info in zip_ref.filelist:
                            if file_info.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                                original_filename = os.path.basename(file_info.filename)
                                unique_filename = f"{uuid.uuid4()}_{original_filename}"
                                file_path = os.path.join(UPLOAD_DIR, unique_filename)

                                with zip_ref.open(file_info) as zip_file:
                                    with open(file_path, 'wb') as target:
                                        target.write(zip_file.read())

                                img = Image.open(file_path)
                                width, height = img.size

                                cur.execute(
                                    """
                                    INSERT INTO images (filename, filepath, width, height, user_id, model_type, consent) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s) 
                                    RETURNING id
                                    """,
                                    (unique_filename, file_path, width, height, user_id, MODEL_TYPE_BIRD_COUNT, consent)
                                )
                                image_id = cur.fetchone()[0]
                                uploaded_image_ids.append(image_id)

                                try:
                                    image = Image.open(file_path)
                                    original_tensor_size = (480, 384)  # Tensor size (width, height)
                                    target_image_size = image.size  # Actual image size (width, height)
                                    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions, subgrid_counts, pred_cnt_flt, subgridcounts_error = demo.run_demo_image_nomongo(image)
                                    scaled_cluster_centers = scale_coordinates(cluster_centers[3], original_tensor_size, target_image_size)
                                    target_width, target_height = target_image_size
                                    cluster_centers_json = json.dumps(scaled_cluster_centers)
                                    cur.execute(
                                        """
                                        INSERT INTO annotations (image_id, width, height, cluster_centers) 
                                        VALUES (%s, %s, %s, %s)
                                        """,
                                        (
                                            image_id,                    
                                            target_width,
                                            target_height,
                                            cluster_centers_json
                                        )
                                    )
                                except Exception as infer_err:
                                    logger.error(f"Inference error for image {image_id}: {infer_err}")

                conn.commit()

        except HTTPException as http_err:
            raise http_err
        except Exception as e:
            logger.error(f"Folder upload error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        finally:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)

    return {
        "message": "Folders uploaded successfully",
        "uploaded_image_ids": uploaded_image_ids
    }
    

def scale_coordinates(cluster_centers, original_size, target_size):
    tensor_width, tensor_height = original_size
    target_width, target_height = target_size

    scale_x = 480 / tensor_width
    scale_y = 384 / tensor_height

    # Flatten the list of lists and scale each point
    scaled_points = [
        {"x": int(point["x"] * scale_x), "y": int(point["y"] * scale_y)}
        for point in cluster_centers
    ]
    return scaled_points



async def upload_images_bird_count(
    request: Request,
    files: List[UploadFile] = File(...),
    model = Depends(get_model),
    user_id = Depends(get_current_user),
    consent: bool = Form(False),
):
    logger.debug(f"Received upload request with consent: {consent}")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
                        (unique_filename, file_path, width, height, user_id, MODEL_TYPE_BIRD_COUNT, consent)
                    )
                    image_id = cur.fetchone()[0]
                    uploaded_ids.append(image_id)
                    
                    try:
                        #cluster_centers=helper_get_cluster1(file)
                        image = Image.open(file_path)
                        original_tensor_size = (480, 384)  # Tensor size (width, height)
                        target_image_size = image.size  # Actual image size (width, height)
                        count, elapsed_time, heatmap_file, cluster_centers, image_dimensions, subgrid_counts, pred_cnt_flt, subgridcounts_error = demo.run_demo_image_nomongo(image)
                        scaled_cluster_centers = scale_coordinates(cluster_centers[3], original_tensor_size, target_image_size)
                        target_width, target_height = target_image_size
                        cluster_centers_json = json.dumps(scaled_cluster_centers)
                        cur.execute(
                            """
                            INSERT INTO annotations (image_id, width, height, cluster_centers) 
                            VALUES (%s, %s, %s, %s)
                            """,
                            (
                                image_id,                    
                                target_width,
                                target_height,
                                cluster_centers_json
                            )
                        )
                    except Exception as infer_err:
                        logger.error(f"Inference error for image {image_id}: {infer_err}")
                        
                conn.commit()
                return {"uploaded_image_ids": uploaded_ids, "user_id": user_id}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"error": str(e)}