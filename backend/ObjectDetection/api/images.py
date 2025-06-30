import os
import re
import torch
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import FileResponse

from Common.shared_utils import logger, get_db_connection, MODEL_TYPE_OBJECT_DETECTION

router = APIRouter()

async def get_images(
    request: Request, 
    user_id: int,
    image_id: Optional[int] = None, 
    class_id: Optional[int] = None,
    box_count_filter: Optional[str] = None,
    query: Optional[str] = Query(None, description="Text query for CLIP search"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if image_id:
                    logger.debug(f"Fetching image with ID: {image_id}, User ID: {user_id}")
                    query = """
                        SELECT filepath FROM images 
                        WHERE id = %s AND model_type = %s AND (consent = true OR user_id = %s)
                        """
                    logger.debug(f"Executing query: {query}")
                    cur.execute(
                        query,
                        (image_id, MODEL_TYPE_OBJECT_DETECTION, user_id)
                    )
                    result = cur.fetchone()
                    logger.debug(f"Database query result: {result}")
                    if not result:
                        raise HTTPException(status_code=404, detail="Image not found")
                    
                    file_path = result['filepath']
                    if not os.path.exists(file_path):
                        raise HTTPException(status_code=404, detail="Image file not found")
                    return FileResponse(file_path)
                
                filter_operator = None
                filter_value = None
                if box_count_filter:
                    match = re.match(r"([=><])(\d+)", box_count_filter)
                    if not match:
                        raise HTTPException(
                            status_code=400, 
                            detail="Invalid format for box_count_filter. Use format like '=5', '>10', '<3'."
                        )
                    filter_operator = match.group(1)
                    filter_value = int(match.group(2))

                if class_id is not None:
                    images_with_user_annotations_query = """
                        SELECT DISTINCT image_id 
                        FROM user_annotated_boxes
                        WHERE image_id IN (
                            SELECT id FROM images 
                            WHERE user_id = %s AND model_type = %s
                        )
                    """
                    cur.execute(images_with_user_annotations_query, (user_id, MODEL_TYPE_OBJECT_DETECTION))
                    images_with_user_annotations = {row[0] for row in cur.fetchall()}
                    
                    user_annotated_query = """
                        SELECT DISTINCT i.id 
                        FROM images i
                        INNER JOIN user_annotated_boxes b ON i.id = b.image_id 
                        WHERE b.class_id = %s AND i.user_id = %s AND i.model_type = %s
                    """
                    cur.execute(user_annotated_query, (class_id, user_id, MODEL_TYPE_OBJECT_DETECTION))
                    user_annotated_image_ids = {row[0] for row in cur.fetchall()}
                    
                    model_predicted_query = """
                        SELECT DISTINCT i.id
                        FROM images i
                        INNER JOIN model_predicted_boxes b ON i.id = b.image_id
                        WHERE b.class_id = %s AND i.user_id = %s AND i.model_type = %s
                        AND i.id NOT IN (
                            SELECT DISTINCT image_id FROM user_annotated_boxes
                            WHERE image_id IN (SELECT id FROM images WHERE user_id = %s AND model_type = %s)
                        )
                    """
                    cur.execute(model_predicted_query, (class_id, user_id, MODEL_TYPE_OBJECT_DETECTION, 
                                                    user_id, MODEL_TYPE_OBJECT_DETECTION))
                    model_predicted_image_ids = {row[0] for row in cur.fetchall()}
                    
                    all_image_ids = user_annotated_image_ids.union(model_predicted_image_ids)
                    initial_image_ids = list(all_image_ids)
                else:
                    cur.execute(
                        "SELECT id FROM images WHERE user_id = %s AND model_type = %s",
                        (user_id, MODEL_TYPE_OBJECT_DETECTION)
                    )
                    initial_image_ids = [row[0] for row in cur.fetchall()]

                if filter_operator and filter_value is not None:
                    filtered_image_ids = []
                    for img_id in initial_image_ids:
                        cur.execute("""
                            SELECT COUNT(*) FROM user_annotated_boxes 
                            WHERE image_id = %s AND user_id = %s
                        """, (img_id, user_id))
                        user_box_count = cur.fetchone()[0]

                        if user_box_count > 0:
                            actual_box_count = user_box_count
                        else:
                            cur.execute("""
                                SELECT COUNT(*) FROM model_predicted_boxes 
                                WHERE image_id = %s
                            """, (img_id,))
                            actual_box_count = cur.fetchone()[0]
                        
                        if filter_operator == '=' and actual_box_count == filter_value:
                            filtered_image_ids.append(img_id)
                        elif filter_operator == '>' and actual_box_count > filter_value:
                            filtered_image_ids.append(img_id)
                        elif filter_operator == '<' and actual_box_count < filter_value:
                            filtered_image_ids.append(img_id)
                    
                    image_ids_list = filtered_image_ids
                else:
                    image_ids_list = initial_image_ids

                if query:
                    proc = request.app.state.clip_processor
                    model = request.app.state.clip_model
                    inputs = proc(text=[query], return_tensors="pt", padding=True).to(model.device)
                    with torch.no_grad():
                        vec = model.get_text_features(**inputs).cpu().numpy().tolist()[0]
                    vec_literal = '[' + ','.join(str(v) for v in vec) + ']'
                    cur.execute(
                        """
                        SELECT image_id
                          FROM image_embeddings
                         WHERE image_id = ANY(%s)
                      ORDER BY embedding <-> %s::vector
                        """,
                        (image_ids_list, vec_literal)
                    )
                    sim_ids_all = [row[0] for row in cur.fetchall()]
                    total = len(sim_ids_all)
                    offset = (page - 1) * page_size
                    sim_page = sim_ids_all[offset: offset + page_size]

                    # fetch filenames for this page of IDs
                    if sim_page:
                        cur.execute(
                            "SELECT id, filename FROM images WHERE id = ANY(%s)",
                            (sim_page,)
                        )
                        rows = cur.fetchall()
                        name_map = {r[0]: r[1] for r in rows}
                        images = [{"id": i, "filename": name_map.get(i)} for i in sim_page]
                    else:
                        images = []

                    return {
                        "images": images,
                        "page": page,
                        "page_size": len(images),
                        "total": total,
                    }

                where_clause = "WHERE id = ANY(%s)"
                params = (image_ids_list,)

                # total matching rows
                cur.execute(f"SELECT COUNT(*) FROM images {where_clause}", params)
                total = cur.fetchone()[0]
                offset = (page - 1) * page_size

                # fetch requested page WITH filename
                cur.execute(
                    f"SELECT id, filename FROM images {where_clause} ORDER BY id LIMIT %s OFFSET %s",
                    (*params, page_size, offset)
                )
                rows = cur.fetchall()
                images = [{"id": row[0], "filename": row[1]} for row in rows]

                return {
                    "images": images,
                    "page": page,
                    "page_size": page_size,
                    "total": total
                }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {"error": str(e)}