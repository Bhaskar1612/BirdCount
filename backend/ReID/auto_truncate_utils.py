import os
import shutil
from datetime import datetime, timedelta
from Common.shared_utils import logger, UPLOAD_DIR, get_db_connection

# --- Configuration ---
# How long should non-consented data be kept before deletion?
# Example: Keep for 6 hours after creation. Adjust as needed.
RETENTION_PERIOD_NON_CONSENTED = timedelta(hours=6)
# -------------------

def truncate_previous_reid_data(user_id: int = None, remove_files: bool = True):
    """
    Deletes all ReID data for a specific user or all users.
    Use with caution, especially without a user_id.

    Args:
        user_id: Optional user ID. If None, *all* ReID data will be deleted.
        remove_files: Whether to remove associated files from disk.
    """
    conn = None
    action = f"user {user_id}" if user_id is not None else "all users"
    logger.info(f"Starting truncation of ReID data for {action}...")

    try:
        conn = get_db_connection()
        if not conn:
            logger.error(f"Truncation failed for {action}: Could not get database connection.")
            return False # Indicate failure

        sessions_to_delete_ids = []
        # Get list of session IDs to delete for file cleanup later
        try:
            with conn.cursor() as cur:
                params = []
                query = "SELECT id FROM reid_sessions"
                if user_id is not None:
                    query += " WHERE user_id = %s"
                    params.append(user_id)
                cur.execute(query, params)
                sessions_to_delete_ids = [row[0] for row in cur.fetchall()]

            if not sessions_to_delete_ids:
                logger.info(f"No ReID sessions found for {action}. Nothing to truncate.")
                return True # Indicate success (nothing to do)

            logger.info(f"Found {len(sessions_to_delete_ids)} sessions to truncate for {action}.")

        except Exception as e:
            logger.error(f"Failed to query sessions for truncation ({action}): {e}")
            return False # Indicate failure

        # Proceed with deletion using a transaction
        deleted_count = 0
        conn.autocommit = False # Start transaction
        try:
            with conn.cursor() as cur:
                # Delete in correct order to respect foreign key constraints
                
                # 1. Delete matches (references query_images, gallery_images)
                cur.execute("DELETE FROM matches WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from matches for {action}.")
                
                # 2. Delete user_feedback (references query_images, gallery_images)
                cur.execute("DELETE FROM user_feedback WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from user_feedback for {action}.")
                
                # 3. Delete query_images (references animal_crops)
                cur.execute("DELETE FROM query_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from query_images for {action}.")
                
                # 4. Delete gallery_images (references animal_crops)
                cur.execute("DELETE FROM gallery_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from gallery_images for {action}.")
                
                # 5. Delete animal_crops (references uploaded_images) - needs JOIN
                cur.execute("""DELETE FROM animal_crops 
                              WHERE uploaded_image_id IN 
                              (SELECT id FROM uploaded_images WHERE session_id = ANY(%s::uuid[]))""", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from animal_crops for {action}.")
                
                # 6. Delete uploaded_images (references reid_sessions)
                cur.execute("DELETE FROM uploaded_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from uploaded_images for {action}.")
                
                # 7. Delete user_gallery_sets (references reid_sessions)
                cur.execute("DELETE FROM user_gallery_sets WHERE upload_session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from user_gallery_sets for {action}.")

                # Finally, delete from the parent table
                sql_sessions = "DELETE FROM reid_sessions WHERE id = ANY(%s::uuid[])"
                cur.execute(sql_sessions, (sessions_to_delete_ids,))
                deleted_count = cur.rowcount
                logger.debug(f"Deleted {deleted_count} records from reid_sessions for {action}.")

            conn.commit() # Commit the transaction
            logger.info(f"Successfully deleted database records for {deleted_count} sessions ({action}).")

        except Exception as e:
            logger.error(f"Database error during truncation transaction for {action}: {e}")
            try:
                conn.rollback()
                logger.warning(f"Rolled back database transaction for {action}.")
            except Exception as rb_e:
                logger.error(f"Failed to rollback transaction: {rb_e}")
            return False # Indicate failure
        
        # --- File Deletion ---
        if remove_files:
            logger.info(f"Starting file deletion for {len(sessions_to_delete_ids)} truncated sessions ({action})...")
            reid_base_dir = os.path.join(UPLOAD_DIR, "reid")
            files_deleted_count = 0
            files_failed_count = 0
            for session_id in sessions_to_delete_ids:
                session_dir = os.path.join(reid_base_dir, str(session_id)) # Ensure session_id is string
                if os.path.exists(session_dir) and os.path.isdir(session_dir):
                    try:
                        shutil.rmtree(session_dir)
                        logger.info(f"Removed session directory: {session_id}")
                        files_deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error removing directory {session_id}: {e}")
                        files_failed_count += 1
                else:
                     logger.warning(f"Session directory not found for deletion: {session_dir}")
            
            logger.info(f"File deletion complete for {action}. Deleted: {files_deleted_count}, Failed: {files_failed_count}")
            # Decide if file deletion failure should change the overall success status
            # For now, we return True if DB part succeeded.
            
        return True # Indicate overall success

    except Exception as e:
        logger.error(f"Unexpected error during truncation for {action}: {e}")
        return False # Indicate failure
    finally:
        if conn:
            conn.autocommit = True # Reset autocommit state is good practice
            conn.close()
        logger.info(f"Truncation process finished for {action}.")


# --- NEW/UPDATED Function for Scheduled Cleanup ---

def cleanup_non_consented_reid_data():
    """
    Finds and deletes ReID sessions where consent=False and which are older
    than RETENTION_PERIOD_NON_CONSENTED. Intended for scheduled execution.
    """
    conn = None
    cutoff_time = datetime.now() - RETENTION_PERIOD_NON_CONSENTED
    logger.info(f"Starting cleanup of non-consented ReID data older than {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}...")

    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Cleanup failed: Could not get database connection.")
            return # Cannot proceed

        sessions_to_delete_ids = []
        # 1. Find session IDs to delete
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM reid_sessions
                    WHERE consent = FALSE AND created_at < %s
                    """,
                    (cutoff_time,)
                )
                sessions_to_delete_ids = [row[0] for row in cur.fetchall()]

            if not sessions_to_delete_ids:
                logger.info("No non-consented sessions found older than the retention period.")
                return # Nothing to do

            logger.info(f"Found {len(sessions_to_delete_ids)} non-consented sessions older than retention period to delete.")

        except Exception as e:
            logger.error(f"Failed to query sessions for cleanup: {e}")
            return # Cannot proceed

        # 2. Delete database records within a transaction
        deleted_count = 0
        conn.autocommit = False # Start transaction
        try:
            with conn.cursor() as cur:
                # Delete in correct order to respect foreign key constraints
                
                # 1. Delete matches (references query_images, gallery_images)
                cur.execute("DELETE FROM matches WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from matches for cleanup.")
                
                # 2. Delete user_feedback (references query_images, gallery_images)
                cur.execute("DELETE FROM user_feedback WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from user_feedback for cleanup.")
                
                # 3. Delete query_images (references animal_crops)
                cur.execute("DELETE FROM query_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from query_images for cleanup.")
                
                # 4. Delete gallery_images (references animal_crops)
                cur.execute("DELETE FROM gallery_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from gallery_images for cleanup.")
                
                # 5. Delete animal_crops (references uploaded_images) - needs JOIN
                cur.execute("""DELETE FROM animal_crops 
                              WHERE uploaded_image_id IN 
                              (SELECT id FROM uploaded_images WHERE session_id = ANY(%s::uuid[]))""", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from animal_crops for cleanup.")
                
                # 6. Delete uploaded_images (references reid_sessions)
                cur.execute("DELETE FROM uploaded_images WHERE session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from uploaded_images for cleanup.")
                
                # 7. Delete user_gallery_sets (references reid_sessions)
                cur.execute("DELETE FROM user_gallery_sets WHERE upload_session_id = ANY(%s::uuid[])", (sessions_to_delete_ids,))
                logger.debug(f"Deleted {cur.rowcount} records from user_gallery_sets for cleanup.")

                # Finally, delete from the parent table
                sql_sessions = "DELETE FROM reid_sessions WHERE id = ANY(%s::uuid[])"
                cur.execute(sql_sessions, (sessions_to_delete_ids,))
                deleted_count = cur.rowcount
                logger.debug(f"Deleted {deleted_count} records from reid_sessions for cleanup.")

            conn.commit() # Commit the transaction
            logger.info(f"Successfully deleted database records for {deleted_count} non-consented sessions.")

        except Exception as e:
            logger.error(f"Database error during cleanup transaction: {e}")
            try:
                conn.rollback()
                logger.warning("Rolled back database transaction for cleanup.")
            except Exception as rb_e:
                logger.error(f"Failed to rollback transaction: {rb_e}")
            # Don't proceed to file deletion if DB failed
            return # Indicate failure or incomplete operation
        
        # 3. Delete Filesystem Data (only if DB deletion succeeded)
        logger.info(f"Starting file deletion for {len(sessions_to_delete_ids)} cleaned-up sessions...")
        reid_base_dir = os.path.join(UPLOAD_DIR, "reid")
        files_deleted_count = 0
        files_failed_count = 0
        for session_id in sessions_to_delete_ids:
            session_dir = os.path.join(reid_base_dir, str(session_id)) # Ensure session_id is string
            if os.path.exists(session_dir) and os.path.isdir(session_dir):
                try:
                    shutil.rmtree(session_dir)
                    logger.info(f"Removed session directory: {session_id}")
                    files_deleted_count += 1
                except Exception as e:
                    logger.error(f"Error removing directory {session_id}: {e}")
                    files_failed_count += 1
            else:
                 logger.warning(f"Session directory not found for deletion: {session_dir}")
        
        logger.info(f"File deletion complete for cleanup. Deleted: {files_deleted_count}, Failed: {files_failed_count}")

    except Exception as e:
        logger.error(f"An unexpected error occurred during the cleanup process: {e}")
        # Rollback if transaction might still be active (though unlikely here)
        if conn and not conn.autocommit:
             try: conn.rollback()
             except Exception: pass
    finally:
        if conn:
            conn.autocommit = True # Reset state
            conn.close()
        logger.info("Non-consented data cleanup process finished.")
