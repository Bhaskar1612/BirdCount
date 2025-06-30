#!/usr/bin/env python3

import os
import psycopg2
import shutil
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
DB_NAME = os.getenv('DB_NAME', 'wildlife_monitoring')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# Upload directory for ReID files
UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')

def clear_reid_data():
    """Clear all ReID data from the database and filesystem"""
    conn = None
    try:
        print(f"Connecting to database {DB_NAME} on {DB_HOST}...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        
        conn.autocommit = False  # Use transactions
        cur = conn.cursor()
        
        print("Disabling foreign key constraints...")
        cur.execute("SET CONSTRAINTS ALL DEFERRED;")
        
        print("Executing TRUNCATE commands...")
        # Order matters due to foreign key constraints
        tables = ["matches", "user_feedback", "query_images", "gallery_images", "reid_sessions"]
        for table in tables:
            print(f"Truncating {table}...")
            cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
        
        conn.commit()
        print("All ReID tables have been truncated successfully!")
        
        # Clear files
        reid_dir = os.path.join(UPLOAD_DIR, "reid")
        if os.path.exists(reid_dir):
            print(f"Removing ReID files from {reid_dir}...")
            for session_dir in os.listdir(reid_dir):
                full_path = os.path.join(reid_dir, session_dir)
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                    print(f"Removed session directory: {session_dir}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if conn:
            conn.close()

def clear_user_reid_data(user_id):
    """Clear ReID data for a specific user"""
    conn = None
    try:
        print(f"Connecting to database {DB_NAME} on {DB_HOST}...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        
        conn.autocommit = False  # Use transactions
        cur = conn.cursor()
        
        print("Disabling foreign key constraints...")
        cur.execute("SET CONSTRAINTS ALL DEFERRED;")
        
        # First, get session IDs for this user
        print(f"Finding sessions for user {user_id}...")
        cur.execute("SELECT id FROM reid_sessions WHERE user_id = %s", (user_id,))
        sessions = [row[0] for row in cur.fetchall()]
        
        if not sessions:
            print(f"No sessions found for user {user_id}")
            return
        
        print(f"Found {len(sessions)} sessions to delete")
        
        # Delete related data in the correct order
        print("Deleting matches...")
        cur.execute("DELETE FROM matches WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting user feedback...")
        cur.execute("DELETE FROM user_feedback WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting query images...")
        cur.execute("DELETE FROM query_images WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting gallery images...")
        cur.execute("DELETE FROM gallery_images WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting sessions...")
        cur.execute("DELETE FROM reid_sessions WHERE id IN %s", (tuple(sessions),))
        
        conn.commit()
        print(f"All ReID data for user {user_id} has been deleted successfully!")
        
        # Clear files
        reid_dir = os.path.join(UPLOAD_DIR, "reid")
        if os.path.exists(reid_dir):
            print(f"Removing ReID files for user {user_id}...")
            for session_id in sessions:
                session_dir = os.path.join(reid_dir, session_id)
                if os.path.exists(session_dir):
                    shutil.rmtree(session_dir)
                    print(f"Removed session directory: {session_id}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if conn:
            conn.close()

def clear_non_consented_data():
    """Clear all non-consented ReID data"""
    conn = None
    try:
        print(f"Connecting to database {DB_NAME} on {DB_HOST}...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        
        conn.autocommit = False  # Use transactions
        cur = conn.cursor()
        
        print("Disabling foreign key constraints...")
        cur.execute("SET CONSTRAINTS ALL DEFERRED;")
        
        # First, get session IDs that are not consented
        print("Finding non-consented sessions...")
        cur.execute("SELECT id FROM reid_sessions WHERE consent = false")
        sessions = [row[0] for row in cur.fetchall()]
        
        if not sessions:
            print("No non-consented sessions found")
            return
        
        print(f"Found {len(sessions)} non-consented sessions to delete")
        
        # Delete related data in the correct order
        print("Deleting matches...")
        cur.execute("DELETE FROM matches WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting user feedback...")
        cur.execute("DELETE FROM user_feedback WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting query images...")
        cur.execute("DELETE FROM query_images WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting gallery images...")
        cur.execute("DELETE FROM gallery_images WHERE session_id IN %s", (tuple(sessions),))
        
        print("Deleting sessions...")
        cur.execute("DELETE FROM reid_sessions WHERE id IN %s", (tuple(sessions),))
        
        conn.commit()
        print("All non-consented ReID data has been deleted successfully!")
        
        # Clear files
        reid_dir = os.path.join(UPLOAD_DIR, "reid")
        if os.path.exists(reid_dir):
            print("Removing non-consented ReID files...")
            for session_id in sessions:
                session_dir = os.path.join(reid_dir, session_id)
                if os.path.exists(session_dir):
                    shutil.rmtree(session_dir)
                    print(f"Removed session directory: {session_id}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Wildlife Monitoring ReID Database Cleanup Utility")
    print("------------------------------------------------")
    print("1. Clear all ReID data")
    print("2. Clear ReID data for a specific user")
    print("3. Clear all non-consented ReID data")
    print("4. Exit")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == "1":
        confirm = input("Are you sure you want to clear ALL ReID data? This cannot be undone. (y/n): ")
        if confirm.lower() == 'y':
            clear_reid_data()
    elif choice == "2":
        user_id = input("Enter user ID: ")
        try:
            user_id = int(user_id)
            confirm = input(f"Are you sure you want to clear ReID data for user {user_id}? This cannot be undone. (y/n): ")
            if confirm.lower() == 'y':
                clear_user_reid_data(user_id)
        except ValueError:
            print("Invalid user ID. Please enter a numeric ID.")
    elif choice == "3":
        confirm = input("Are you sure you want to clear all non-consented ReID data? This cannot be undone. (y/n): ")
        if confirm.lower() == 'y':
            clear_non_consented_data()
    elif choice == "4":
        print("Exiting...")
    else:
        print("Invalid choice. Exiting...")
    
    print("Done!")