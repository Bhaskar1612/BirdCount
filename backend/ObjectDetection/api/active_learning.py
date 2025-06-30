from fastapi import APIRouter, HTTPException, Query, Request, Depends
from Common.shared_utils import logger, get_db_connection, MODEL_TYPE_OBJECT_DETECTION
from Common.api.auth import get_current_user

router = APIRouter()

async def get_active_learning_images(
    request: Request, 
    limit: int = Query(5, description="Limit must be one of 5, 10, or 20", ge=1, le=20),
    user_id: int = Depends(get_current_user),
):
    if limit not in [5, 10, 20]:
        raise HTTPException(status_code=400, detail="Limit must be 5, 10, or 20")

    algorithm_type = "enms_diversity"
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT i.id, i.filename, i.filepath, i.width, i.height 
                    FROM images i
                    JOIN active_learning_rankings r ON i.id = r.image_id 
                    LEFT JOIN active_learning_boxes a ON a.image_id = i.id AND a.user_id = %s
                    WHERE i.consent = true 
                      AND i.model_type = %s 
                      AND a.image_id IS NULL
                      AND r.algorithm_type = %s
                    ORDER BY r.ranking_score
                    LIMIT %s
                """
                cur.execute(query, (user_id, MODEL_TYPE_OBJECT_DETECTION, algorithm_type, limit))
                rows = cur.fetchall()
                images = [dict(row) for row in rows]
                
                return images
    except Exception as e:
        logger.error(f"Error fetching active learning images: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")