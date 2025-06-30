import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
from PIL import Image
from tqdm import tqdm

from Common.shared_utils import logger, get_db_connection, UPLOAD_DIR
from .Megadetector_wrapper import MegaDetectorWrapper
from .Megadescriptor_wrapper import MegaDescriptorWrapper
from .MiewIDWrapper import MiewIDWrapper

class ReIDPipeline:
    def __init__(self, megadetector: MegaDetectorWrapper = None, feature_extractor = None, model_type: str = "megadescriptor"):
        self.detector = megadetector or MegaDetectorWrapper()
        self.model_type = model_type
        
        # Initialize appropriate feature extractor based on model type
        if feature_extractor is not None:
            self.descriptor = feature_extractor
        elif model_type == "miewid":
            logger.info("Initializing MiewID feature extractor")
            self.descriptor = MiewIDWrapper()
        else:
            logger.info("Initializing MegaDescriptor feature extractor")
            self.descriptor = MegaDescriptorWrapper()
        
    def get_species_code(self, species_id: int) -> str:
        """Get species code for ID generation"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT species_code, name FROM classes WHERE id = %s", (species_id,))
                result = cur.fetchone()
                if result and result[0]:
                    return result[0]
                # Generate code from name if not set
                if result and result[1]:
                    name = result[1].upper()
                    code = name[:3] if len(name) >= 3 else name
                    # Update the database with generated code
                    cur.execute("UPDATE classes SET species_code = %s WHERE id = %s", (code, species_id))
                    conn.commit()
                    return code
                return "UNK"
        finally:
            conn.close()
    
    def get_next_individual_id(self, species_id: int) -> int:
        """Get next individual ID for a species"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Initialize counter if not exists
                cur.execute(
                    "INSERT INTO species_individual_counters (species_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (species_id,)
                )
                # Get and increment counter
                cur.execute(
                    "UPDATE species_individual_counters SET next_individual_id = next_individual_id + 1 WHERE species_id = %s RETURNING next_individual_id - 1",
                    (species_id,)
                )
                result = cur.fetchone()
                if result:
                    conn.commit()
                    return result[0]
                return 1
        finally:
            conn.close()
    
    def generate_animal_id(self, species_id: int, sequence: int = 1, is_no_detection: bool = False) -> str:
        """Generate hierarchical animal ID: {SPECIES_CODE}_{INDIVIDUAL_ID}_{SEQUENCE}"""
        species_code = self.get_species_code(species_id)
        
        if is_no_detection:
            individual_id = self.get_next_individual_id(species_id)
            return f"{species_code}_UNK_{individual_id:03d}"
        
        individual_id = self.get_next_individual_id(species_id)
        if sequence > 1:
            return f"{species_code}_{individual_id:03d}_{sequence:02d}"
        return f"{species_code}_{individual_id:03d}"
    
    def assign_query_identities(self, session_id: str, similarity_threshold: float = 0.8):
        """Assign animal IDs to query images based on top matches"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get session info
                cur.execute("SELECT species_id FROM reid_sessions WHERE id = %s", (session_id,))
                result = cur.fetchone()
                if not result:
                    return
                species_id = result[0]
                
                # Get query images and their top matches
                cur.execute(
                    """
                    SELECT q.id, m.gallery_image_id, m.score, g.animal_id
                    FROM query_images q
                    LEFT JOIN matches m ON q.id = m.query_image_id AND m.rank = 1
                    LEFT JOIN gallery_images g ON m.gallery_image_id = g.id
                    WHERE q.session_id = %s
                    ORDER BY q.id
                    """,
                    (session_id,)
                )
                
                for query_id, gallery_id, score, gallery_animal_id in cur.fetchall():
                    if score and score >= similarity_threshold and gallery_animal_id:
                        # Assign existing gallery animal ID
                        cur.execute(
                            """UPDATE query_images 
                               SET assigned_animal_id = %s, assignment_confidence = %s, is_new_individual = false
                               WHERE id = %s""",
                            (gallery_animal_id, score, query_id)
                        )
                        logger.info(f"Query {query_id} assigned to existing animal {gallery_animal_id} (confidence: {score:.3f})")
                    else:
                        # Create new individual ID
                        new_animal_id = self.generate_animal_id(species_id, sequence=1, is_no_detection=False)
                        confidence = score if score else 0.0
                        cur.execute(
                            """UPDATE query_images 
                               SET assigned_animal_id = %s, assignment_confidence = %s, is_new_individual = true
                               WHERE id = %s""",
                            (new_animal_id, confidence, query_id)
                        )
                        logger.info(f"Query {query_id} assigned new animal ID {new_animal_id} (confidence: {confidence:.3f})")
                
                conn.commit()
        finally:
            conn.close()
        
    def process_uploaded_images(self, session_id: str, upload_dir: str):
        """Process all uploaded images for a session"""
        session_dir = os.path.join(upload_dir, "reid", session_id)
        crops_dir = os.path.join(session_dir, "crops")
        os.makedirs(crops_dir, exist_ok=True)
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get session info
                cur.execute(
                    "SELECT species_id, query_pre_cropped, gallery_pre_cropped FROM reid_sessions WHERE id = %s",
                    (session_id,)
                )
                session_info = cur.fetchone()
                if not session_info:
                    logger.error(f"Session {session_id} not found")
                    return
                    
                species_id, query_pre_cropped, gallery_pre_cropped = session_info
                
                # Get uploaded images
                cur.execute(
                    "SELECT id, image_path, image_type, is_pre_cropped FROM uploaded_images WHERE session_id = %s",
                    (session_id,)
                )
                images = cur.fetchall()
                
                total = len(images)
                for idx, (img_id, img_path, img_type, is_pre_cropped) in enumerate(images):
                    full_path = os.path.join(session_dir, img_path)
                    
                    if is_pre_cropped:
                        # Handle pre-cropped images
                        self._process_precropped_image(cur, img_id, full_path, img_type, crops_dir, species_id)
                    else:
                        # Detect and crop
                        self._detect_and_crop_image(cur, img_id, full_path, img_type, crops_dir, species_id)
                    
                    # Update progress
                    progress = int(((idx + 1) / total) * 50)
                    cur.execute(
                        "UPDATE reid_sessions SET progress_percentage = %s WHERE id = %s",
                        (progress, session_id)
                    )
                    conn.commit()
        finally:
            if conn:
                conn.close()
                
    def _process_precropped_image(self, cur, img_id: int, img_path: str, img_type: str, crops_dir: str, species_id: int):
        """Handle pre-cropped images"""
        img = Image.open(img_path)
        if img.mode == 'RGBA':
            logger.info("img mode is RGBA, converting and saving to RGB")
            img = img.convert('RGB')
            img.save(img_path, 'JPEG')
        
        width, height = img.size
        
        crop_coords = {"x": 0, "y": 0, "width": width, "height": height, "confidence": 1.0}
        crop_filename = f"{img_type}_{img_id}_1.jpg"
        crop_path = os.path.join(crops_dir, crop_filename)
        
        # Copy image to crops
        img.save(crop_path)
        
        # Generate systematic animal ID for gallery images
        animal_id = None
        if img_type == 'gallery':
            animal_id = self.generate_animal_id(species_id, sequence=1, is_no_detection=False)
        
        # Store in database
        cur.execute(
            """INSERT INTO animal_crops 
               (uploaded_image_id, crop_coordinates, animal_sequence, animal_id, 
                detection_confidence, cropped_image_path)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (img_id, json.dumps(crop_coords), 1, animal_id, 1.0, f"crops/{crop_filename}")
        )
        
    def _detect_and_crop_image(self, cur, img_id: int, img_path: str, img_type: str, crops_dir: str, species_id: int):
        """Detect animals and create crops"""
        try:
            detections = self.detector.detect_animals(img_path)
            detections = self.detector.filter_detections(detections)  # Filter for animals only
        except Exception as e:
            logger.warning(f"Detection failed for {img_path}: {str(e)}")
            detections = []
        
        if not detections:
            logger.warning(f"No animals detected in {img_path}")
            # Create placeholder entry for images with no detections
            self._create_no_detection_entry(cur, img_id, img_path, img_type, crops_dir, species_id)
            return
            
        
        img = Image.open(img_path)
        # if img.mode == 'RGBA':
        #     img = img.convert('RGB')
        
        for seq, detection in enumerate(detections, 1):
            bbox = detection['bbox']
            confidence = detection['confidence']
            
            # Get crop coordinates
            crop_coords = self.detector.get_crop_coordinates(bbox, img.size[::-1])  # PIL size is (width, height)
            
            # Crop image
            cropped = img.crop((crop_coords['x_min'], crop_coords['y_min'], 
                               crop_coords['x_max'], crop_coords['y_max']))
            
            # Save crop
            crop_filename = f"{img_type}_{img_id}_{seq}.jpg"
            crop_path = os.path.join(crops_dir, crop_filename)
            cropped.save(crop_path)
            
            # Generate systematic animal ID for gallery
            animal_id = None
            if img_type == 'gallery':
                animal_id = self.generate_animal_id(species_id, sequence=seq, is_no_detection=False)
            
            # Store crop info
            crop_data = {
                "x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3],
                "confidence": confidence
            }
            
            cur.execute(
                """INSERT INTO animal_crops 
                   (uploaded_image_id, crop_coordinates, animal_sequence, animal_id,
                    detection_confidence, cropped_image_path)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (img_id, json.dumps(crop_data), seq, animal_id, confidence, f"crops/{crop_filename}")
            )
    
    def _create_no_detection_entry(self, cur, img_id: int, img_path: str, img_type: str, crops_dir: str, species_id: int):
        """Create entry for images where no animals were detected"""
        try:
            img = Image.open(img_path)
            if img.mode == 'RGBA':
                logger.info("img mode is RGBA, converting and saving to RGB")
                img = img.convert('RGB')
                img.save(img_path, 'JPEG')
            width, height = img.size
        except Exception as e:
            logger.error(f"Failed to process no-detection image {img_path}: {str(e)}")
            return
        
        # Copy original image to crops directory as placeholder
        crop_filename = f"{img_type}_{img_id}_no_detection.jpg"
        crop_path = os.path.join(crops_dir, crop_filename)
        img.save(crop_path)
        
        # Create crop coordinates that cover the whole image
        crop_coords = {"x": 0, "y": 0, "width": width, "height": height, "confidence": 0.0}
        
        # Generate systematic animal ID for gallery images (no detection case)
        animal_id = None
        if img_type == 'gallery':
            animal_id = self.generate_animal_id(species_id, sequence=1, is_no_detection=True)
        
        # Store in database with special marker
        cur.execute(
            """INSERT INTO animal_crops 
               (uploaded_image_id, crop_coordinates, animal_sequence, animal_id,
                detection_confidence, cropped_image_path)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (img_id, json.dumps(crop_coords), 0, animal_id, 0.0, f"crops/{crop_filename}")
        )
            
    def create_query_gallery_entries(self, session_id: str):
        """Create entries in query_images and gallery_images tables"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get session info
                cur.execute(
                    "SELECT species_id, use_global_gallery, user_id FROM reid_sessions WHERE id = %s",
                    (session_id,)
                )
                result = cur.fetchone()
                if not result:
                    logger.error(f"Session {session_id} not found")
                    return
                    
                species_id, use_global_gallery, user_id = result
                
                # Create query entries
                cur.execute(
                    """INSERT INTO query_images (animal_crop_id, session_id)
                       SELECT ac.id, %s FROM animal_crops ac
                       JOIN uploaded_images ui ON ac.uploaded_image_id = ui.id
                       WHERE ui.session_id = %s AND ui.image_type = 'query'""",
                    (session_id, session_id)
                )
                
                # Create gallery entries if not using global
                if not use_global_gallery:
                    cur.execute(
                        """INSERT INTO gallery_images 
                           (animal_crop_id, session_id, species_id, animal_id, user_id, is_global)
                           SELECT ac.id, %s, %s, ac.animal_id, %s, ui.is_global
                           FROM animal_crops ac
                           JOIN uploaded_images ui ON ac.uploaded_image_id = ui.id
                           WHERE ui.session_id = %s AND ui.image_type = 'gallery'""",
                        (session_id, species_id, user_id, session_id)
                    )
                    
                conn.commit()
        finally:
            if conn:
                conn.close()

    def extract_features_and_match(self, session_id: str, batch_size: int = 16, top_k: int = 10):
        """Extract features and compute matches"""
        conn = get_db_connection()
        session_dir = os.path.join(UPLOAD_DIR, "reid", session_id)
        
        try:
            with conn.cursor() as cur:
                # Get session info
                cur.execute(
                    "SELECT species_id, use_global_gallery FROM reid_sessions WHERE id = %s",
                    (session_id,)
                )
                result = cur.fetchone()
                if not result:
                    logger.error(f"Session {session_id} not found")
                    return
                    
                species_id, use_global_gallery = result
                
                # Get query images - separate those with detections from those without
                cur.execute(
                    """SELECT q.id, ac.cropped_image_path, ac.detection_confidence
                       FROM query_images q
                       JOIN animal_crops ac ON q.animal_crop_id = ac.id
                       WHERE q.session_id = %s
                       ORDER BY q.id""",
                    (session_id,)
                )
                query_data = cur.fetchall()
                
                if not query_data:
                    logger.error(f"No query images found for session {session_id}")
                    return
                
                # Get gallery images - Modified query to get session_id correctly
                if use_global_gallery:
                    cur.execute(
                        """SELECT g.id, ac.cropped_image_path, ui.session_id
                           FROM gallery_images g
                           JOIN animal_crops ac ON g.animal_crop_id = ac.id
                           JOIN uploaded_images ui ON ac.uploaded_image_id = ui.id
                           WHERE g.species_id = %s AND g.is_global = true""",
                        (species_id,)
                    )
                else:
                    cur.execute(
                        """SELECT g.id, ac.cropped_image_path, %s as session_id
                           FROM gallery_images g
                           JOIN animal_crops ac ON g.animal_crop_id = ac.id
                           WHERE g.session_id = %s""",
                        (session_id, session_id)
                    )
                gallery_data = cur.fetchall()
                
                if not gallery_data:
                    logger.error(f"No gallery images found for session {session_id}")
                    return
                
                # Separate queries with detections from those without
                query_paths = []
                query_ids = []
                no_detection_queries = []
                
                for q_id, crop_path, detection_confidence in query_data:
                    full_path = os.path.join(session_dir, crop_path)
                    if os.path.exists(full_path):
                        if detection_confidence > 0:  # Has animal detection
                            query_paths.append(full_path)
                            query_ids.append(q_id)
                        else:  # No animal detection
                            no_detection_queries.append((q_id, crop_path))
                    else:
                        logger.warning(f"Query image not found: {full_path}")
                        
                gallery_paths = []
                gallery_ids = []
                for g_id, crop_path, g_session_id in gallery_data:
                    if use_global_gallery and g_session_id:
                        # For global gallery, use the original session path
                        full_path = os.path.join(UPLOAD_DIR, "reid", g_session_id, crop_path)
                        logger.info(f"Loading global gallery image from session {g_session_id}: {crop_path}")
                    else:
                        full_path = os.path.join(session_dir, crop_path)
                        logger.info(f"Loading user gallery image: {crop_path}")
                        
                    if os.path.exists(full_path):
                        gallery_paths.append(full_path)
                        gallery_ids.append(g_id)
                    else:
                        logger.warning(f"Gallery image not found: {full_path}")
                        
                # Handle queries with no animal detections (log but don't process for feature extraction)
                if no_detection_queries:
                    logger.info(f"Found {len(no_detection_queries)} queries with no animal detections")
                
                # Only proceed with feature extraction if we have detections
                if query_paths and gallery_paths:
                    # Extract features
                    logger.info(f"Extracting features for {len(query_paths)} queries and {len(gallery_paths)} gallery images")
                    try:
                        query_features = self.descriptor.extract_features(query_paths, batch_size)
                        gallery_features = self.descriptor.extract_features(gallery_paths, batch_size)
                    except Exception as e:
                        logger.error(f"Feature extraction failed: {str(e)}")
                        query_features = gallery_features = np.array([])
                    
                    # Check dimensions
                    logger.info(f"Query features shape: {query_features.shape}")
                    logger.info(f"Gallery features shape: {gallery_features.shape}")
                    
                    # Ensure features are 2D
                    if len(query_features.shape) == 1:
                        query_features = query_features.reshape(1, -1)
                    if len(gallery_features.shape) == 1:
                        gallery_features = gallery_features.reshape(1, -1)
                    
                    # Ensure we have features
                    if query_features.shape[0] == 0 or gallery_features.shape[0] == 0:
                        logger.error("No features extracted")
                    else:
                        # Store embeddings in appropriate column based on model type
                        embedding_column = "embedding_miewid" if self.model_type == "miewid" else "embedding"
                        
                        for i, q_id in enumerate(query_ids):
                            if i < query_features.shape[0]:
                                embedding = query_features[i].tolist()
                                cur.execute(
                                    f"UPDATE query_images SET {embedding_column} = %s, model_used = %s WHERE id = %s",
                                    (json.dumps(embedding), self.model_type, q_id)
                                )
                                
                        for i, g_id in enumerate(gallery_ids):
                            if i < gallery_features.shape[0]:
                                embedding = gallery_features[i].tolist()
                                cur.execute(
                                    f"UPDATE gallery_images SET {embedding_column} = %s, model_used = %s WHERE id = %s",
                                    (json.dumps(embedding), self.model_type, g_id)
                                )
                                
                        # Compute similarities
                        try:
                            similarities = self.descriptor.compute_similarities(query_features, gallery_features)
                            logger.info(f"Similarity matrix shape: {similarities.shape}")
                        except Exception as e:
                            logger.error(f"Similarity computation failed: {str(e)}")
                            similarities = np.zeros((len(query_ids), len(gallery_ids)))
                        
                        # Create matches
                        for i, q_id in enumerate(query_ids):
                            if i < similarities.shape[0]:
                                sims = similarities[i]
                                top_indices = np.argsort(-sims)[:min(top_k, len(gallery_ids))]
                                
                                for rank, idx in enumerate(top_indices):
                                    if idx < len(gallery_ids):
                                        cur.execute(
                                            """INSERT INTO matches (session_id, query_image_id, gallery_image_id, score, rank)
                                               VALUES (%s, %s, %s, %s, %s)""",
                                            (session_id, q_id, gallery_ids[idx], float(sims[idx]), rank + 1)
                                        )
                else:
                    logger.info("No queries with animal detections to process for feature matching")
                
                # Update session status (regardless of whether matches were created)
                cur.execute(
                    "UPDATE reid_sessions SET processing_status = 'completed', progress_percentage = 100 WHERE id = %s",
                    (session_id,)
                )
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error in feature extraction: {str(e)}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def run_complete_pipeline(self, session_id: str, user_id: int):
        """Run the complete ReID pipeline"""
        logger.info(f"Starting ReID pipeline for session {session_id} with model type: {self.model_type}")
        
        try:
            # Update status
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reid_sessions SET processing_status = 'processing' WHERE id = %s",
                    (session_id,)
                )
                conn.commit()
            conn.close()
                
            # Process images
            self.process_uploaded_images(session_id, UPLOAD_DIR)
            
            # Create query/gallery entries
            self.create_query_gallery_entries(session_id)
            
            # Extract features and match
            self.extract_features_and_match(session_id)
            
            # Assign identities to query images
            self.assign_query_identities(session_id, similarity_threshold=0.8)
            
            logger.info(f"Completed ReID pipeline for session {session_id}")

        except Exception as e:
            logger.error(f"Problem in loading the pipeline : {e}")
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reid_sessions SET processing_status = 'failed' WHERE id = %s",
                    (session_id,)
                )
                conn.commit()
            conn.close()