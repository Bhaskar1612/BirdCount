from fastapi import APIRouter, HTTPException, Query, Request, Depends,APIRouter, UploadFile, File, Form, Request, HTTPException
from Common.shared_utils import logger, get_db_connection, MODEL_TYPE_BIRD_COUNT
from Common.api.auth import get_current_user
from pydantic import BaseModel
from typing import List,Tuple
import json
import cv2
from BirdCount.api.get_boxes import select_top_patches_from_image
import numpy as np

router = APIRouter()

async def get_active_learning_images_birdcount(
    request: Request, 
    limit: int = Query(5, description="Limit must be one of 5, 10, or 20", ge=1, le=20),
    user_id: int = Depends(get_current_user),
):
    if limit not in [5, 10, 20]:
        raise HTTPException(status_code=400, detail="Limit must be 5, 10, or 20")
    # user_id = await get_user_id(request)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                        SELECT * FROM active_learning_birdcount
                        WHERE NOT %s = ANY(user_ids)
                        ORDER BY created_at ASC
                        LIMIT %s;
                        """
                cur.execute(query, (user_id, limit))
                rows = cur.fetchall()
                images = [dict(row) for row in rows]
                return images
    except Exception as e:
        logger.error(f"Error fetching active learning images: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    

class Box(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class BirdCountInput(BaseModel):
    image_id: int
    boxes: List[Box]
    dots: List[dict] = []  # Optional, default to empty list


async def add_active_learning_birdcount_entry(data: BirdCountInput):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                print(data.boxes)
                insert_query = """
                    INSERT INTO active_learning_birdcount (image_id, boxes, dots)
                    VALUES (%s, %s, %s);
                """
                cur.execute(
                    insert_query,
                    (
                        data.image_id,
                        json.dumps([box.dict() for box in data.boxes]),
                        json.dumps(data.dots)
                    )
                )
                conn.commit()
                return {"message": "Entry added successfully"}
    except Exception as e:
        logger.error(f"Error inserting active learning entry: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    


class Dot(BaseModel):
    x: float
    y: float

class UpdateBirdCountDotsInput(BaseModel):
    image_id: int
    user_id: int
    dots: List[Dot]

@router.post("/active_learning_birdcount/update")
async def update_active_learning_birdcount(input_data: UpdateBirdCountDotsInput):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Add user_id to the array if not already present
                update_user_query = """
                    UPDATE active_learning_birdcount
                    SET user_ids = array_append(user_ids, %s)
                    WHERE image_id = %s AND NOT %s = ANY(user_ids);
                """
                cur.execute(update_user_query, (input_data.user_id, input_data.image_id, input_data.user_id))

                # 2. Append new sublist of dots (for one box) to the existing list of dot-lists
                new_dots_sublist_json = json.dumps([dot.dict() for dot in input_data.dots])  # one box's dots
                append_dots_query = """
                    UPDATE active_learning_birdcount
                    SET dots = dots || to_jsonb(ARRAY[%s]::jsonb[])
                    WHERE image_id = %s;
                """
                cur.execute(append_dots_query, (new_dots_sublist_json, input_data.image_id))

                conn.commit()
                return {"message": "Entry updated successfully"}
    except Exception as e:
        logger.error(f"Error updating active learning entry: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    

@router.post("/active-learning/auto-boxes/")
async def generate_and_add_boxes_for_active_learning(
    request: Request,
    file: UploadFile = File(...),
    image_id: int = Form(...)
):
    try:
        # Read and decode image
        image_data = await file.read()
        np_img = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        # Get top boxes from image
        selected_boxes = select_top_patches_from_image(
            img,
            num_total_patches=50,
            num_top_patches=5,
            max_patch_area_ratio=0.33,
            seed=42
        )
        print("Select Boxes",selected_boxes)

        # Convert to Pydantic Box models
        box_models = [Box(x1=box[0], y1=box[1], x2=box[2], y2=box[3]) for box in selected_boxes]

        # Create BirdCountInput and call add function
        data = BirdCountInput(
            image_id=image_id,
            boxes=box_models
        )

        # Add to DB
        result = await add_active_learning_birdcount_entry(data)

        # Return the selected boxes
        return {
            "message": result["message"],
            "boxes": [box.dict() for box in box_models]
        }

    except Exception as e:
        logger.error(f"Error processing image and adding boxes: {e}")
        raise HTTPException(status_code=500, detail="Error processing image")