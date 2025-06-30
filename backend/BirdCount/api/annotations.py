import json
import psycopg2
from psycopg2.extras import DictCursor
from typing import List
from fastapi import APIRouter, HTTPException, Request, Depends,Query
from Common.shared_utils import logger, DB_CONFIG, MODEL_TYPE_BIRD_COUNT
from Common.api.auth import get_current_user

router = APIRouter()

def scale_coordinates(cluster_centers, original_size, target_size):
    tensor_width, tensor_height = original_size
    target_width, target_height = target_size
    scale_x = 480 / tensor_width
    scale_y = 384 / tensor_height
    return [
        {"x": int(point["x"] * scale_x), "y": int(point["y"] * scale_y)}
        for point in cluster_centers
    ]

@router.get("/annotations")
async def get_annotations(
    request: Request, 
    image_id: int = Query(..., description="Image ID to fetch annotations"),
    user_id: int = Depends(get_current_user),
):
    try:
        with psycopg2.connect(**DB_CONFIG, cursor_factory=DictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.cluster_centers FROM annotations a 
                    JOIN images i ON a.image_id = i.id 
                    WHERE i.id = %s AND i.user_id = %s
                    """,
                    (image_id, user_id)
                )
                result = cur.fetchone()  # Fetch a single result

        print(result["cluster_centers"])
        if result and result["cluster_centers"]:
            cluster_centers = result["cluster_centers"]   # Convert to JSON
            
        else:
            cluster_centers = []
        return {"annotations": cluster_centers}
    except Exception as e:
        logger.error(f"Database error in GET /annotations: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/annotations")
async def upload_annotations(
    request: Request, 
    image_id: int, 
    cluster_centers: List[dict],
    user_id: int = Depends(get_current_user),
):
    try:
        print(cluster_centers)
        with psycopg2.connect(**DB_CONFIG, cursor_factory=DictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM images 
                    WHERE id = %s AND user_id = %s AND model_type = %s
                    """,
                    (image_id, user_id, MODEL_TYPE_BIRD_COUNT)
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=403, detail="Not authorized to modify this image")
                
                cur.execute("SELECT width, height FROM annotations WHERE image_id = %s", (image_id,))
                result = cur.fetchone()
                if result:
                    target_width, target_height = result
                else:
                    target_width, target_height = 0, 0
                    
                cur.execute("DELETE FROM annotations WHERE image_id = %s", (image_id,))
                cluster_centers_json = json.dumps(cluster_centers)
                
                cur.execute(
                    """
                    INSERT INTO annotations (image_id, width, height, cluster_centers)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (image_id, target_width, target_height, cluster_centers_json)
                )
                conn.commit()
        return {"message": "Annotation uploaded successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Annotation upload error in POST /annotations: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")