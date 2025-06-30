from fastapi import APIRouter, Request, HTTPException, Query, Body, Depends
from typing import List
from Common.shared_utils import logger, get_db_connection
from Common.api.auth import get_current_user

router = APIRouter()

@router.get("/bounding-boxes")
async def get_boxes(
    request: Request, 
    image_id: int = Query(...),
    box_type: str = Query("user", enum=["user", "active"]),
    user_id: int = Depends(get_current_user),
):
    table_name = "user_annotated_boxes" if box_type == "user" else "active_learning_boxes"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT EXISTS (
                        SELECT 1
                        FROM {table_name}
                        WHERE image_id = %s AND user_id = %s
                    )
                """, (image_id, user_id))
                
                exists = cur.fetchone()[0]

                if not exists:
                    cur.execute("""
                        SELECT b.id, b.image_id, b.class_id, b.x, b.y, b.width, b.height, b.confidence, b.created_at
                        FROM model_predicted_boxes b
                        JOIN images i ON b.image_id = i.id
                        WHERE i.id = %s
                    """, (image_id,))
                    boxes = cur.fetchall()
                else:
                    cur.execute(f"""
                        SELECT b.id, b.image_id, b.class_id, b.x, b.y, b.width, b.height, b.confidence, b.created_at
                        FROM {table_name} b
                        JOIN images i ON b.image_id = i.id
                        WHERE i.id = %s AND b.user_id = %s
                    """, (image_id, user_id))
                    boxes = cur.fetchall()
                return {"boxes": boxes}
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"error": str(e)}

@router.post("/bounding-boxes")
async def upload_boxes(
    request: Request, 
    image_id: int = Query(...), 
    boxes: List[dict] = Body(...),
    box_type: str = Query("user", enum=["user", "active"]),
    user_id: int = Depends(get_current_user),
):
    table_name = "user_annotated_boxes" if box_type == "user" else "active_learning_boxes"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM images WHERE id = %s AND (user_id = %s OR consent = true) AND model_type = 1", 
                    (image_id, user_id)
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=403, detail="Not authorized to modify this image")
                
                cur.execute(f"DELETE FROM {table_name} WHERE image_id = %s AND user_id = %s", (image_id, user_id))
                
                for box in boxes:
                    cur.execute(f"""
                        INSERT INTO {table_name} (image_id, user_id, class_id, x, y, width, height, confidence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        image_id,
                        user_id,
                        box["class_id"],
                        box["x"],
                        box["y"],
                        box["width"],
                        box["height"],
                        1.0
                    ))
                
                conn.commit()
                return {"message": "Boxes uploaded successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Box upload error: {e}")
        return {"error": str(e)}