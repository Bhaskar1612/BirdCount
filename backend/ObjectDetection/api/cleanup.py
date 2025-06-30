from fastapi import APIRouter, HTTPException, Depends
import os
from Common.shared_utils import logger, get_db_connection, MODEL_TYPE_OBJECT_DETECTION
from Common.api.auth import get_current_user

router = APIRouter()

@router.delete("/cleanup")
async def cleanup_non_consented(
    user_id: int = Depends(get_current_user)
):
    try:
        perform_cleanup(user_id)
        return {"message": "Non-consented images cleaned up successfully"}
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail="Error during cleanup")


def perform_cleanup(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filepath FROM images 
                WHERE consent = false AND model_type = %s AND user_id = %s
            """, (MODEL_TYPE_OBJECT_DETECTION, user_id))
            files_to_delete = cur.fetchall()
            
            for (filepath,) in files_to_delete:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            cur.execute("""
                DELETE FROM user_annotated_boxes 
                WHERE image_id IN (
                    SELECT id FROM images 
                    WHERE consent = false AND model_type = %s AND user_id = %s
                )
            """, (MODEL_TYPE_OBJECT_DETECTION, user_id))
            cur.execute("""
                DELETE FROM model_predicted_boxes 
                WHERE image_id IN (
                    SELECT id FROM images 
                    WHERE consent = false AND model_type = %s AND user_id = %s
                )
            """, (MODEL_TYPE_OBJECT_DETECTION, user_id))
            cur.execute("""
                DELETE FROM images 
                WHERE consent = false AND model_type = %s AND user_id = %s
            """, (MODEL_TYPE_OBJECT_DETECTION, user_id))
            conn.commit()