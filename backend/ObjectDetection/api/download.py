import io
import zipfile
from zipfile import ZipFile
import cv2
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from Common.shared_utils import get_db_connection, logger, MODEL_TYPE_OBJECT_DETECTION
from Common.api.auth import get_current_user

router = APIRouter()

async def download_object_detection_images(
    request: Request, 
    user_id: int = Depends(get_current_user),
):
    try:
        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM classes")
                    species_map = {row[0]: row[1] for row in cur.fetchall()}

                    cur.execute("""
                        SELECT i.id, i.filepath, i.filename 
                        FROM images i 
                        WHERE i.user_id = %s AND i.model_type = %s
                    """, (user_id, MODEL_TYPE_OBJECT_DETECTION))
                    images = cur.fetchall()

                    for img_id, filepath, filename in images:
                        cur.execute("""
                            SELECT class_id, x, y, width, height 
                            FROM user_annotated_boxes 
                            WHERE image_id = %s AND user_id = %s
                        """, (img_id, user_id))
                        boxes = cur.fetchall()
                        
                        if not boxes:
                            cur.execute("""
                                SELECT class_id, x, y, width, height 
                                FROM model_predicted_boxes 
                                WHERE image_id = %s
                            """, (img_id,))
                            boxes = cur.fetchall()

                        img = cv2.imread(filepath)
                        if img is None:
                            logger.error(f"Could not read image: {filepath}")
                            continue

                        h, w = img.shape[:2]

                        for box in boxes:
                            class_id, x_center, y_center, width, height = box
                            species_name = species_map.get(class_id, f'Unknown ({class_id})')

                            x1 = int(x_center - width/2)
                            y1 = int(y_center - height/2)
                            x2 = int(x_center + width/2)
                            y2 = int(y_center + height/2)

                            x1 = max(0, min(x1, w))
                            y1 = max(0, min(y1, h))
                            x2 = max(0, min(x2, w))
                            y2 = max(0, min(y2, h))

                            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
                            
                            font = cv2.FONT_HERSHEY_SIMPLEX
                            font_scale = 0.8
                            thickness = 2
                            padding = 5

                            (text_width, text_height), _ = cv2.getTextSize(species_name, font, font_scale, thickness)
                            cv2.rectangle(
                                img, (x1 + padding, y1 + padding), 
                                (x1 + text_width + padding * 2, y1 + text_height + padding * 2),
                                (0, 255, 0), -1
                            )
                            cv2.putText(
                                img, species_name,
                                (x1 + padding, y1 + text_height + padding), 
                                font, font_scale, (255, 255, 255),
                                thickness, cv2.LINE_AA
                            )

                        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                        _, buffer = cv2.imencode('.jpg', img, encode_param)
                        zip_file.writestr(filename, buffer.tobytes())
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer, 
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename=annotated-images.zip'}
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))