import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse

from Common.shared_utils import logger, get_db_connection, MODEL_TYPE_BIRD_COUNT

from fastapi.responses import JSONResponse

router = APIRouter()
    

async def get_images_birdcount(
    request: Request, 
    user_id: int ,
    image_id: Optional[int] = None,
):
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if image_id:
                    # Serve the image file directly
                    cur.execute(
                        """
                        SELECT filepath FROM images 
                        WHERE id = %s AND model_type = %s AND (user_id = %s OR consent = true)
                        """,
                        (image_id, MODEL_TYPE_BIRD_COUNT, user_id)
                    )
                    result = cur.fetchone()
                    if not result:
                        raise HTTPException(status_code=404, detail="Image not found")
                    
                    file_path = result[0]
                    if not os.path.exists(file_path):
                        raise HTTPException(status_code=404, detail="Image file not found")

                    return FileResponse(file_path)

                else:
                    # Return a list of image metadata
                    cur.execute(
                        "SELECT id FROM images WHERE user_id = %s AND model_type = %s",
                        (user_id, MODEL_TYPE_BIRD_COUNT)
                    )
                    images = [{"id": row[0], "url": f"/get_images_birdcount?image_id={row[0]}"} for row in cur.fetchall()]
                    return JSONResponse(content={"images": images})
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Database error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)