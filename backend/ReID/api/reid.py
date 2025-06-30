import os
import uuid
import zipfile
import tarfile
import shutil
import json
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Query, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel


import io
import cv2
import numpy as np
from datetime import datetime

from Common.shared_utils import logger, UPLOAD_DIR, get_db_connection
from Common.api.auth import get_current_user
from ReID.wrapper.reid_model_integration import ReIDPipeline
from ReID.auto_truncate_utils import truncate_previous_reid_data

router = APIRouter()

MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB , to limit the file size upload

# Pipeline will be initialized per session with appropriate model

def run_reid_pipeline_with_model(session_id: str, user_id: int, model_type: str):
    """Initialize and run ReID pipeline with specified model"""
    try:
        logger.info(f"Initializing ReID pipeline with model: {model_type}")
        pipeline = ReIDPipeline(model_type=model_type)
        pipeline.run_complete_pipeline(session_id, user_id)
    except Exception as e:
        logger.error(f"Pipeline execution failed for session {session_id}: {str(e)}")
        # Update session status to failed
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reid_sessions SET processing_status = 'failed' WHERE id = %s",
                    (session_id,)
                )
                conn.commit()
        except:
            pass
        finally:
            if conn:
                conn.close()
        raise

def create_session_folder(session_id: str) -> str:
    """Create folder structure for session with separate query/gallery directories"""
    folder_path = os.path.join(UPLOAD_DIR, "reid", session_id)
    os.makedirs(os.path.join(folder_path, "originals", "query"), exist_ok=True)
    os.makedirs(os.path.join(folder_path, "originals", "gallery"), exist_ok=True)
    os.makedirs(os.path.join(folder_path, "crops"), exist_ok=True)
    return folder_path

def extract_archive(file: UploadFile, extract_to: str) -> List[str]:
    """Extract images from archive"""
    temp_file = os.path.join(extract_to, file.filename)
    
    with open(temp_file, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    extracted_files = []
    
    if file.filename.lower().endswith('.zip'):
        with zipfile.ZipFile(temp_file, 'r') as zf:
            for info in zf.infolist():
                if info.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    if '__MACOSX' not in info.filename and not info.filename.startswith('._'):
                        zf.extract(info, extract_to)
                        extracted_files.append(os.path.basename(info.filename))
    
    elif file.filename.lower().endswith(('.tar', '.tar.gz', '.tgz')):
        mode = 'r:gz' if file.filename.lower().endswith(('.gz', '.tgz')) else 'r'
        with tarfile.open(temp_file, mode) as tf:
            for member in tf.getmembers():
                if member.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    if '__MACOSX' not in member.name and not os.path.basename(member.name).startswith('._'):
                        tf.extract(member, extract_to)
                        extracted_files.append(os.path.basename(member.name))
    
    os.remove(temp_file)
    
    # Flatten directory structure
    for filename in extracted_files:
        for root, dirs, files in os.walk(extract_to):
            if filename in files and root != extract_to:
                src = os.path.join(root, filename)
                dst = os.path.join(extract_to, filename)
                if src != dst:
                    shutil.move(src, dst)
    
    # Clean empty directories
    for root, dirs, files in os.walk(extract_to, topdown=False):
        if root != extract_to and not os.listdir(root):
            os.rmdir(root)
    
    return extracted_files

@router.get("/species")
async def get_species_list(user_id: int = Depends(get_current_user)):
    """Get available species"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM classes ORDER BY name")
        return {"species": [{"id": row[0], "name": row[1]} for row in cur.fetchall()]}

@router.get("/global-gallery-status/{species_id}")
async def check_global_gallery(species_id: int, user_id: int = Depends(get_current_user)):
    """Check global gallery availability"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM gallery_images WHERE species_id = %s AND is_global = true",
            (species_id,)
        )
        count = cur.fetchone()[0]
        return {"has_global_gallery": count > 0, "gallery_size": count}


# def validate_file_size(file: UploadFile):
#     if not file:
#         return True
    
#     # Get file size by seeking to end
#     file.file.seek(0, 2)  # Seek to end
#     file_size = file.file.tell()
#     file.file.seek(0)  # Reset to beginning
    
#     return file_size <= MAX_FILE_SIZE

# # Add this validation after the existing format validation
# if not validate_file_size(query_set):
#     raise HTTPException(
#         status_code=400, 
#         detail="Query set file exceeds the 1GB size limit"
#     )

# if gallery_set and not validate_file_size(gallery_set):
#     raise HTTPException(
#         status_code=400, 
#         detail="Gallery set file exceeds the 1GB size limit"
#     )




@router.post("/upload")
async def upload_reid_images(
    background_tasks: BackgroundTasks,
    species_id: int = Form(...),
    use_global_gallery: bool = Form(False),
    query_set: UploadFile = File(...),
    gallery_set: Optional[UploadFile] = File(None),
    query_pre_cropped: bool = Form(False),
    gallery_pre_cropped: bool = Form(False),
    clear_previous: bool = Form(False),
    consent: bool = Form(True),
    feature_model: str = Form("megadescriptor"),  # New parameter for model selection
    user_id: int = Depends(get_current_user)
):
    """Upload ReID images"""
    
    logger.info(f"Upload request - Species: {species_id}, Use global: {use_global_gallery}, Model: {feature_model}")
    
    # Validate model choice
    if feature_model not in ["megadescriptor", "miewid"]:
        raise HTTPException(status_code=400, detail="Invalid feature model. Must be 'megadescriptor' or 'miewid'")
    
    # Validation
    if not use_global_gallery and not gallery_set:
        raise HTTPException(status_code=400, detail="Gallery set required when not using global gallery")

    def validate_file_size(file: UploadFile):
        if not file:
            return True
        
        # Get file size by seeking to end
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        return file_size <= MAX_FILE_SIZE

    # Add this validation after the existing format validation
    if not validate_file_size(query_set):
        raise HTTPException(
            status_code=400, 
            detail="Query set file exceeds the 1GB size limit"
        )

    if gallery_set and not validate_file_size(gallery_set):
        raise HTTPException(
            status_code=400, 
            detail="Gallery set file exceeds the 1GB size limit"
        )


    
    # Check if global gallery exists when requested
    if use_global_gallery:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM gallery_images WHERE species_id = %s AND is_global = true",
                    (species_id,)
                )
                count = cur.fetchone()[0]
                if count == 0:
                    raise HTTPException(
                        status_code=400, 
                        detail="No global gallery available for this species. Please upload your own gallery set."
                    )
                logger.info(f"Found {count} global gallery images for species {species_id}")
        except Exception as e:
            logger.error(f"Error checking global gallery: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        finally:
            conn.close()
    
    if clear_previous:
        try:
            truncate_previous_reid_data(user_id=user_id, remove_files=True)
        except Exception as e:
            logger.error(f"Error clearing previous data: {str(e)}")
    
    # Create session
    session_id = str(uuid.uuid4())
    logger.info(f"Creating session {session_id}")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO reid_sessions 
                   (id, user_id, species_id, use_global_gallery, query_pre_cropped, 
                    gallery_pre_cropped, consent, processing_status, feature_model) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'uploading', %s)""",
                (session_id, user_id, species_id, use_global_gallery, 
                 query_pre_cropped, gallery_pre_cropped, consent, feature_model)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()
    
    # Extract files
    try:
        folder_path = create_session_folder(session_id)
        query_originals_path = os.path.join(folder_path, "originals", "query")
        gallery_originals_path = os.path.join(folder_path, "originals", "gallery")
        
        logger.info(f"Extracting query set: {query_set.filename}")
        query_files = extract_archive(query_set, query_originals_path)
        if not query_files:
            raise HTTPException(status_code=400, detail="No images found in query archive")
        logger.info(f"Extracted {len(query_files)} query images")
        
        gallery_files = []
        if gallery_set:
            logger.info(f"Extracting gallery set: {gallery_set.filename}")
            gallery_files = extract_archive(gallery_set, gallery_originals_path)
            if not gallery_files:
                raise HTTPException(status_code=400, detail="No images found in gallery archive")
            logger.info(f"Extracted {len(gallery_files)} gallery images")
        
        # Store image records
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Store query images
                for qf in query_files:
                    cur.execute(
                        """INSERT INTO uploaded_images 
                           (session_id, image_path, image_type, user_id, species_id, is_pre_cropped) 
                           VALUES (%s, %s, 'query', %s, %s, %s)""",
                        (session_id, f"originals/query/{qf}", user_id, species_id, query_pre_cropped)
                    )
                
                # Store gallery images
                for gf in gallery_files:
                    cur.execute(
                        """INSERT INTO uploaded_images 
                           (session_id, image_path, image_type, user_id, species_id, is_pre_cropped, is_global) 
                           VALUES (%s, %s, 'gallery', %s, %s, %s, %s)""",
                        (session_id, f"originals/gallery/{gf}", user_id, species_id, gallery_pre_cropped, consent)
                    )
                
                conn.commit()
                logger.info("Stored image records in database")
        except Exception as e:
            logger.error(f"Error storing image records: {str(e)}")
            raise
        finally:
            conn.close()
        
        # Process in background
        logger.info(f"Starting background processing with {feature_model} model")
        background_tasks.add_task(run_reid_pipeline_with_model, session_id, user_id, feature_model)
        
        return {"session_id": session_id, "message": "Upload successful, processing started"}
        
    except Exception as e:
        logger.error(f"Error during upload processing: {str(e)}", exc_info=True)
        
        # Clean up on error
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM uploaded_images WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM reid_sessions WHERE id = %s", (session_id,))
                conn.commit()
            conn.close()
        except:
            pass
            
        # Remove files
        try:
            folder_path = os.path.join(UPLOAD_DIR, "reid", session_id)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
        except:
            pass
            
        if isinstance(e, HTTPException):
            raise
        else:
            raise HTTPException(status_code=500, detail=f"Upload processing error: {str(e)}")

@router.get("/results/{session_id}")
async def get_results(session_id: str, user_id: int = Depends(get_current_user)):
    """Get ReID results"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Check session
        cur.execute(
            "SELECT processing_status, progress_percentage FROM reid_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id)
        )
        session_data = cur.fetchone()
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        status, progress = session_data
        
        if status != 'completed':
            return {
                "session_id": session_id,
                "processing_status": status,
                "progress_percentage": progress or 0,
                "results": []
            }
        
        # Get results - use LEFT JOIN to include queries without matches
        cur.execute(
            """
            SELECT q.id, qac.cropped_image_path, qui.image_path,
                   m.rank, m.score, gac.cropped_image_path, g.animal_id, gui.image_path, g.id, g.session_id
            FROM query_images q
            JOIN animal_crops qac ON q.animal_crop_id = qac.id
            JOIN uploaded_images qui ON qac.uploaded_image_id = qui.id
            LEFT JOIN matches m ON q.id = m.query_image_id
            LEFT JOIN gallery_images g ON m.gallery_image_id = g.id
            LEFT JOIN animal_crops gac ON g.animal_crop_id = gac.id
            LEFT JOIN uploaded_images gui ON gac.uploaded_image_id = gui.id
            WHERE q.session_id = %s
            ORDER BY q.id, m.rank
            """,
            (session_id,)
        )
        
        # Group by query
        results = {}
        for row in cur.fetchall():
            q_id, q_crop, q_orig, rank, score, g_crop, animal_id, g_orig, g_id, g_session_id = row
            
            if q_id not in results:
                results[q_id] = {
                    "query_image": q_crop,
                    "query_image_id": q_id,
                    "original_image_path": q_orig,
                    "matches": []
                }
            
            # Only add match if it exists (handles LEFT JOIN NULLs)
            if rank is not None and score is not None:
                results[q_id]["matches"].append({
                    "image_path": g_crop,
                    "id": animal_id,
                    "gallery_image_id": g_id,
                    "score": score,
                    "original_image_path": g_orig,
                    "session_id": g_session_id
                })
        
        return {
            "session_id": session_id,
            "processing_status": "completed",
            "progress_percentage": 100,
            "results": list(results.values())
        }

@router.get("/sessions")
async def get_sessions(user_id: int = Depends(get_current_user)):
    """Get user sessions"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.created_at, c.name, r.processing_status, r.progress_percentage,
                   r.use_global_gallery, r.feature_model,
                   (SELECT COUNT(*) FROM uploaded_images WHERE session_id = r.id AND image_type = 'query') as query_count,
                   (SELECT COUNT(*) FROM uploaded_images WHERE session_id = r.id AND image_type = 'gallery') as gallery_count
            FROM reid_sessions r
            JOIN classes c ON r.species_id = c.id
            WHERE r.user_id = %s
            ORDER BY r.created_at DESC
            """,
            (user_id,)
        )
        
        sessions = []
        for row in cur.fetchall():
            sessions.append({
                "id": row[0],
                "created_at": row[1].strftime("%Y-%m-%d %H:%M:%S"),
                "species_name": row[2],
                "processing_status": row[3],
                "progress_percentage": row[4] or 0,
                "use_global_gallery": row[5],
                "feature_model": row[6] or "megadescriptor",  # Default fallback for old sessions
                "query_count": row[7],
                "gallery_count": row[8]
            })
        
        return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: int = Depends(get_current_user)):
   """Delete a session"""
   conn = get_db_connection()
   with conn.cursor() as cur:
       # Verify ownership
       cur.execute("SELECT id FROM reid_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
       if not cur.fetchone():
           raise HTTPException(status_code=404, detail="Session not found")
       
       # Delete in correct order
       cur.execute("DELETE FROM matches WHERE session_id = %s", (session_id,))
       cur.execute("DELETE FROM user_feedback WHERE session_id = %s", (session_id,))
       cur.execute("DELETE FROM query_images WHERE session_id = %s", (session_id,))
       cur.execute("DELETE FROM gallery_images WHERE session_id = %s", (session_id,))
       cur.execute(
           """DELETE FROM animal_crops 
              WHERE uploaded_image_id IN (SELECT id FROM uploaded_images WHERE session_id = %s)""",
           (session_id,)
       )
       cur.execute("DELETE FROM uploaded_images WHERE session_id = %s", (session_id,))
       cur.execute("DELETE FROM reid_sessions WHERE id = %s", (session_id,))
       conn.commit()
   
   # Delete files
   folder_path = os.path.join(UPLOAD_DIR, "reid", session_id)
   if os.path.exists(folder_path):
       shutil.rmtree(folder_path)
   
   return {"message": "Session deleted successfully"}


class FeedbackRequest(BaseModel):
    session_id: str
    query_image_id: int
    gallery_image_id: int
    is_correct: bool

@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user_id: int = Depends(get_current_user)
):
    """Submit match feedback"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verify session ownership
            cur.execute("SELECT id FROM reid_sessions WHERE id = %s AND user_id = %s", 
                       (request.session_id, user_id))
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Check existing feedback
            cur.execute(
                """SELECT id FROM user_feedback 
                   WHERE session_id = %s AND query_image_id = %s AND gallery_image_id = %s""",
                (request.session_id, request.query_image_id, request.gallery_image_id)
            )
            existing = cur.fetchone()
            
            if existing:
                cur.execute(
                    "UPDATE user_feedback SET is_correct = %s, timestamp = NOW() WHERE id = %s",
                    (request.is_correct, existing[0])
                )
                feedback_id = existing[0]
            else:
                cur.execute(
                    """INSERT INTO user_feedback (session_id, query_image_id, gallery_image_id, is_correct)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (request.session_id, request.query_image_id, request.gallery_image_id, request.is_correct)
                )
                feedback_id = cur.fetchone()[0]
            
            conn.commit()
            return {"message": "Feedback recorded", "id": feedback_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback error: {str(e)}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/feedback")
async def get_feedback(session_id: str, user_id: int = Depends(get_current_user)):
   """Get feedback for a session"""
   conn = get_db_connection()
   with conn.cursor() as cur:
       cur.execute(
           """SELECT f.query_image_id, f.gallery_image_id, f.is_correct
              FROM user_feedback f
              JOIN reid_sessions s ON f.session_id = s.id
              WHERE f.session_id = %s AND s.user_id = %s""",
           (session_id, user_id)
       )
       
       feedback = []
       for row in cur.fetchall():
           feedback.append({
               "query_image_id": row[0],
               "gallery_image_id": row[1],
               "is_correct": row[2]
           })
       
       return feedback



@router.get("/download/{session_id}")
async def download_results(session_id: str, user_id: int = Depends(get_current_user)):
    """Download results as ZIP with images"""
    import io
    import cv2
    from datetime import datetime
    
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # Verify ownership and completion
            cur.execute(
                "SELECT processing_status FROM reid_sessions WHERE id = %s AND user_id = %s",
                (session_id, user_id)
            )
            session_data = cur.fetchone()
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            if session_data[0] != 'completed':
                raise HTTPException(status_code=400, detail="Processing not completed")
            
            # Get results with all paths
            cur.execute(
                """
                SELECT q.id, qac.cropped_image_path, qui.image_path,
                       m.rank, m.score, gac.cropped_image_path, g.animal_id,
                       f.is_correct, m.gallery_image_id, g.session_id, qac.crop_coordinates
                FROM query_images q
                JOIN animal_crops qac ON q.animal_crop_id = qac.id
                JOIN uploaded_images qui ON qac.uploaded_image_id = qui.id
                JOIN matches m ON q.id = m.query_image_id
                JOIN gallery_images g ON m.gallery_image_id = g.id
                JOIN animal_crops gac ON g.animal_crop_id = gac.id
                LEFT JOIN user_feedback f ON (f.query_image_id = q.id AND f.gallery_image_id = g.id)
                WHERE q.session_id = %s
                ORDER BY q.id, m.rank
                """,
                (session_id,)
            )
            
            results = cur.fetchall()
        
        # Create ZIP
        zip_buffer = io.BytesIO()
        session_dir = os.path.join(UPLOAD_DIR, "reid", session_id)
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Group by query
            query_groups = {}
            for row in results:
                q_id = row[0]
                if q_id not in query_groups:
                    query_groups[q_id] = []
                query_groups[q_id].append(row)
            
            # Create collages
            for q_id, matches in query_groups.items():
                if not matches:
                    continue
                    
                # Read query image
                query_crop_path = os.path.join(session_dir, matches[0][1])
                if not os.path.exists(query_crop_path):
                    continue
                    
                query_img = cv2.imread(query_crop_path)
                if query_img is None:
                    continue
                
                # Create collage
                h, w = query_img.shape[:2]
                collage_width = w * 6
                collage_height = h * 2
                collage = np.ones((collage_height, collage_width, 3), dtype=np.uint8) * 255
                
                # Place query image
                collage[0:h, 0:w] = query_img
                cv2.putText(collage, "Query", (10, h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                
                # Place top 10 matches
                for i, match in enumerate(matches[:10]):
                    if i >= 10:
                        break
                        
                    gallery_session_id = match[9]  # g.session_id from query
                    if gallery_session_id and gallery_session_id != session_id:
                        # Gallery image from different session (global gallery)
                        gallery_crop_path = os.path.join(UPLOAD_DIR, "reid", gallery_session_id, match[5])
                    else:
                        # Gallery image from current session
                        gallery_crop_path = os.path.join(session_dir, match[5])
                    
                    if os.path.exists(gallery_crop_path):
                        gallery_img = cv2.imread(gallery_crop_path)
                        if gallery_img is not None:
                            gallery_img = cv2.resize(gallery_img, (w, h))
                            
                            # Position in grid
                            row = 0 if i < 5 else 1
                            col = (i % 5) + 1
                            x_offset = col * w
                            y_offset = row * h
                            
                            # # Add feedback border if exists
                            # if match[7] is not None:  # has feedback
                            #     color = (0, 255, 0) if match[7] else (0, 0, 255)
                            #     cv2.rectangle(gallery_img, (0, 0), (w-1, h-1), color, 3)
                            
                            # collage[y_offset:y_offset+h, x_offset:x_offset+w] = gallery_img
                            
                            # # Add text
                            # text = f"#{match[3]} ID:{match[6]} Score:{match[4]:.3f}"
                            # cv2.putText(collage, text, (x_offset + 5, y_offset + h + 25), 
                            #            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)


                            # Add feedback border if exists
                            if match[7] is not None:
                                color = (0, 255, 0) if match[7] else (0, 0, 255)
                                cv2.rectangle(gallery_img, (0, 0), (w-1, h-1), color, 3)

                            # Place the image
                            collage[y_offset:y_offset+h, x_offset:x_offset+w] = gallery_img

                            # Draw semi-transparent black background
                            overlay = collage.copy()
                            cv2.rectangle(overlay,
                                        (x_offset, y_offset),
                                        (x_offset + 200, y_offset + 40),
                                        (0, 0, 0),
                                        -1)
                            alpha = 0.6
                            cv2.addWeighted(overlay, alpha, collage, 1 - alpha, 0, dst=collage)

                            # Add text
                            cv2.putText(collage, f"Rank: {match[3]}, ID: {match[6]}", 
                                        (x_offset + 5, y_offset + 15),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.45,
                                        (255, 255, 255),
                                        1,
                                        cv2.LINE_AA)

                            cv2.putText(collage, f"Score: {match[4]:.3f}", 
                                        (x_offset + 5, y_offset + 32),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.45,
                                        (255, 255, 255),
                                        1,
                                        cv2.LINE_AA)

                
                # Save collage
                _, buffer = cv2.imencode('.jpg', collage)
                zf.writestr(f"query_{q_id}_results.jpg", buffer.tobytes())
            
            # Create annotated original images with bounding boxes
            processed_originals = set()  # Track to avoid duplicates
            for q_id, matches in query_groups.items():
                if not matches:
                    continue
                    
                # Get original image path and crop coordinates
                original_path_rel = matches[0][2]  # qui.image_path from query
                crop_coords_json = matches[0][10]  # qac.crop_coordinates
                
                if not crop_coords_json or original_path_rel in processed_originals:
                    continue
                    
                original_path = os.path.join(session_dir, original_path_rel)
                if not os.path.exists(original_path):
                    continue
                    
                try:
                    # Parse crop coordinates (handle both string and dict cases)
                    if isinstance(crop_coords_json, str):
                        crop_coords = json.loads(crop_coords_json)
                    elif isinstance(crop_coords_json, dict):
                        crop_coords = crop_coords_json
                    else:
                        logger.warning(f"Unexpected crop_coords type: {type(crop_coords_json)}")
                        continue
                    
                    # Read original image
                    original_img = cv2.imread(original_path)
                    if original_img is None:
                        continue
                        
                    # Draw bounding box
                    if 'x' in crop_coords and 'y' in crop_coords:
                        x = int(crop_coords['x'])
                        y = int(crop_coords['y'])
                        w = int(crop_coords['width'])
                        h = int(crop_coords['height'])
                        confidence = crop_coords.get('confidence', 0.0)
                        
                        # Draw rectangle (green for detected animals, red for no detection)
                        color = (0, 255, 0) if confidence > 0 else (0, 0, 255)
                        cv2.rectangle(original_img, (x, y), (x + w, y + h), color, 3)
                        
                        # Add confidence text
                        if confidence > 0:
                            text = f"Animal: {confidence:.2f}"
                        else:
                            text = "No detection"
                        cv2.putText(original_img, text, (x, y - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                    
                    # Save annotated original
                    _, buffer = cv2.imencode('.jpg', original_img)
                    filename = f"annotated_originals/query_{q_id}_original_with_bbox.jpg"
                    zf.writestr(filename, buffer.tobytes())
                    processed_originals.add(original_path_rel)
                    
                except Exception as e:
                    logger.warning(f"Failed to annotate original image {original_path}: {str(e)}")
                    continue
            
            # Add CSV
            csv_content = "query_id,rank,gallery_animal_id,score,feedback\n"
            for row in results:
                q_id, _, _, rank, score, _, animal_id, is_correct, _, _, _ = row
                feedback = "correct" if is_correct is True else "incorrect" if is_correct is False else "no_feedback"
                csv_content += f"{q_id},{rank},{animal_id},{score:.4f},{feedback}\n"
            
            zf.writestr("results.csv", csv_content)
            
            # Add info file
            info = f"ReID Results - Session {session_id}\n"
            info += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            info += f"Total queries: {len(query_groups)}\n"
            info += f"Total matches: {len(results)}\n"
            info += f"\nContents:\n"
            info += f"- query_X_results.jpg: Collage showing query and top matches\n"
            info += f"- annotated_originals/: Original images with bounding boxes\n"
            info += f"- results.csv: Detailed match scores and feedback\n"
            zf.writestr("session_info.txt", info)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=reid_results_{session_id}.zip"}
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/images/{session_id}/{image_path:path}")
async def get_image(session_id: str, image_path: str, user_id: int = Depends(get_current_user)):
   """Get session image"""
   conn = get_db_connection()
   
   # Verify ownership or global gallery access
   with conn.cursor() as cur:
       # Check if user owns the session
       cur.execute("SELECT id FROM reid_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
       user_owns_session = cur.fetchone() is not None
       
       if not user_owns_session:
           # Check if this is a global gallery image that the user can access
           # Extract crop filename from image_path
           crop_filename = image_path.split('/')[-1] if '/' in image_path else image_path
           
           cur.execute("""
               SELECT 1 FROM gallery_images g
               JOIN animal_crops ac ON g.animal_crop_id = ac.id
               WHERE g.session_id = %s AND g.is_global = true 
               AND ac.cropped_image_path LIKE %s
           """, (session_id, f"%{crop_filename}"))
           
           is_global_image = cur.fetchone() is not None
           
           if not is_global_image:
               raise HTTPException(status_code=403, detail="Access denied")
   
   file_path = os.path.join(UPLOAD_DIR, "reid", session_id, image_path)
   
   if not os.path.exists(file_path):
       raise HTTPException(status_code=404, detail="Image not found")
   
   return FileResponse(file_path)

# Note: Global images are stored in their original session directories, not in a centralized location
# Use the regular /images/{session_id}/{image_path:path} endpoint instead

@router.get("/gallery-preview/{species_id}")
async def get_gallery_preview(
   species_id: int,
   limit: int = Query(8, ge=1, le=20),
   user_id: int = Depends(get_current_user)
):
   """Get gallery preview for species"""
   conn = get_db_connection()
   with conn.cursor() as cur:
       cur.execute(
           """
           SELECT ac.cropped_image_path, g.animal_id, g.is_global, g.session_id
           FROM gallery_images g
           JOIN animal_crops ac ON g.animal_crop_id = ac.id
           WHERE g.species_id = %s AND (g.user_id = %s OR g.is_global = true)
           ORDER BY g.is_global DESC, g.created_at DESC
           LIMIT %s
           """,
           (species_id, user_id, limit)
       )
       
       preview = []
       for row in cur.fetchall():
           preview.append({
               "image_path": row[0],
               "animal_id": row[1],
               "is_global": row[2],
               "session_id": row[3]
           })
       
       return {"preview_images": preview}


      # Add gallery management endpoints
@router.get("/gallery-sets")
async def get_user_gallery_sets(user_id: int = Depends(get_current_user)):
    """Get user's gallery sets by species"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT c.id, c.name,
                       COUNT(DISTINCT g.animal_id) as animal_count,
                       COUNT(g.id) as image_count,
                       MAX(g.created_at) as last_updated
                FROM gallery_images g
                JOIN classes c ON g.species_id = c.id
                WHERE g.user_id = %s AND g.is_global = false
                GROUP BY c.id, c.name
                ORDER BY c.name
                """,
                (user_id,)
            )
            
            sets = []
            for row in cur.fetchall():
                sets.append({
                    "species_id": row[0],
                    "species_name": row[1],
                    "animal_count": row[2],
                    "image_count": row[3],
                    "last_updated": row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else None
                })
            
            return {"gallery_sets": sets}
    finally:
        if conn:
            conn.close()

@router.get("/gallery-sets/{species_id}/preview")
async def preview_gallery_set(
    species_id: int,
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user)
):
    """Preview images in a gallery set"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Log debug information
            logger.info(f"Gallery preview request: species_id={species_id}, user_id={user_id}, limit={limit}")
            
            # Check total gallery images for this species and user (including global)
            cur.execute(
                "SELECT COUNT(*) FROM gallery_images WHERE species_id = %s AND user_id = %s",
                (species_id, user_id)
            )
            total_count = cur.fetchone()[0]
            logger.info(f"Total gallery images for user {user_id}, species {species_id}: {total_count}")
            
            # Check how many are global vs private
            cur.execute(
                "SELECT is_global, COUNT(*) FROM gallery_images WHERE species_id = %s AND user_id = %s GROUP BY is_global",
                (species_id, user_id)
            )
            counts = cur.fetchall()
            logger.info(f"Gallery images breakdown: {counts}")
            
            cur.execute(
                """
                SELECT ac.cropped_image_path, g.animal_id, g.session_id, g.is_global
                FROM gallery_images g
                JOIN animal_crops ac ON g.animal_crop_id = ac.id
                WHERE g.species_id = %s AND g.user_id = %s
                ORDER BY g.created_at DESC
                LIMIT %s
                """,
                (species_id, user_id, limit)
            )
            
            images = []
            for row in cur.fetchall():
                images.append({
                    "image_path": row[0],
                    "animal_id": row[1],
                    "session_id": row[2],
                    "is_global": row[3]
                })
            
            return {"images": images}
    finally:
        if conn:
            conn.close()

@router.get("/gallery-sets/{species_id}/download")
async def download_gallery_set(
    species_id: int,
    user_id: int = Depends(get_current_user)
):
    """Download all gallery images for a species"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get species name
            cur.execute("SELECT name FROM classes WHERE id = %s", (species_id,))
            species_name = cur.fetchone()[0]
            
            # Get all gallery images (both private and contributed to global)
            cur.execute(
                """
                SELECT ac.cropped_image_path, g.animal_id, g.session_id
                FROM gallery_images g
                JOIN animal_crops ac ON g.animal_crop_id = ac.id
                WHERE g.species_id = %s AND g.user_id = %s
                ORDER BY g.animal_id, g.created_at
                """,
                (species_id, user_id)
            )
            images = cur.fetchall()
            
        if not images:
            raise HTTPException(status_code=404, detail="No images found")
        
        # Create ZIP
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for crop_path, animal_id, session_id in images:
                # Find the actual file in the session directory
                full_path = os.path.join(UPLOAD_DIR, "reid", session_id, crop_path)
                
                if os.path.exists(full_path):
                    # Add to zip with organized structure
                    filename = f"{animal_id}/{os.path.basename(crop_path)}"
                    with open(full_path, 'rb') as f:
                        zf.writestr(filename, f.read())
                else:
                    logger.warning(f"Gallery image not found: {full_path}")
            
            # Add metadata
            metadata = f"Gallery Set: {species_name}\n"
            metadata += f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            metadata += f"Total images: {len(images)}\n"
            metadata += f"Unique animals: {len(set(img[1] for img in images))}\n"
            zf.writestr("metadata.txt", metadata)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=gallery_{species_name.replace(' ', '_')}.zip"}
        )
    finally:
        if conn:
            conn.close() 