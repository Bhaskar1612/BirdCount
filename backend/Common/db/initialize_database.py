import psycopg2
from psycopg2 import Error
from pathlib import Path
import yaml
from Common.shared_utils import logger, DB_CONFIG
from dotenv import load_dotenv
load_dotenv()

def get_db_connection(dbname="postgres"):
    try:
        logger.info("trying to connect with database")
        return psycopg2.connect(**{**DB_CONFIG, "dbname": dbname})
    except Error as e:
        logger.error(f"Connection failed: {e}")
        return None

def check_classes_populated():
    conn = None
    cursor = None
    try:
        conn = get_db_connection(DB_CONFIG["dbname"])
        if not conn:
            return False, 0, 0
            
        cursor = conn.cursor()
        
        yaml_path = Path(__file__).parent.parent.parent / "ObjectDetection/models/YOLO/data/wii_aite_2022_testing.yaml"
        with open(yaml_path, 'r', encoding='utf-8') as f:
            expected_count = len(yaml.safe_load(f).get('names', []))
        
        cursor.execute("SELECT COUNT(*) FROM classes")
        actual_count = cursor.fetchone()[0]
        return actual_count == expected_count, actual_count, expected_count
        
    except Exception as e:
        logger.error(f"Error checking classes: {e}")
        return False, 0, 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def parse_schema_file():
    schema_path = Path(__file__).parent.parent / "db/schema.sql"
    expected_schema = {}
    
    with open(schema_path, 'r') as f:
        content = f.read()
        tables = content.split('CREATE TABLE IF NOT EXISTS')
        for table in tables[1:]:
            lines = table.strip().split('\n')
            table_name = lines[0].strip().split()[0]
            columns = []
            
            for line in lines[1:]:
                line = line.strip().strip(',').strip(');').strip()
                if not line or line.startswith('--'):
                    continue
                # skip index/extension or any other CREATE statements
                if line.upper().startswith("CREATE"):
                    continue
                # skip foreign‑key constraint lines
                if line.upper().startswith("REFERENCES"):
                    continue
                if line.upper().startswith("UNIQUE") or line.upper().startswith("PRIMARY") or line.upper().startswith("FOREIGN"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0]
                    col_type = parts[1].split('(')[0].upper()
                    columns.append((col_name, col_type))
                    
            expected_schema[table_name] = columns
            
    return expected_schema

def check_reid_schema_compatibility():
    """
    Check if the existing database has the new ReID schema structure
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(DB_CONFIG["dbname"])
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if reid_sessions has the new columns (including MiewID support)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'reid_sessions' 
            AND column_name IN ('use_global_gallery', 'query_pre_cropped', 'gallery_pre_cropped', 'processing_status', 'feature_model')
        """)
        new_columns = [row[0] for row in cursor.fetchall()]
        
        required_new_columns = ['use_global_gallery', 'query_pre_cropped', 'gallery_pre_cropped', 'processing_status', 'feature_model']
        
        if len(new_columns) < len(required_new_columns):
            logger.info("Reid_sessions table missing new columns - schema recreation needed")
            return False
        
        # Check if new ReID tables exist
        new_reid_tables = ['uploaded_images', 'animal_crops', 'user_gallery_sets']
        for table in new_reid_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (table,))
            if not cursor.fetchone()[0]:
                logger.info(f"New ReID table {table} missing - schema recreation needed")
                return False
        
        # Check if MiewID embedding columns exist
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'query_images' 
            AND column_name IN ('model_used', 'embedding_miewid')
        """)
        query_miewid_cols = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'gallery_images' 
            AND column_name IN ('model_used', 'embedding_miewid')
        """)
        gallery_miewid_cols = [row[0] for row in cursor.fetchall()]
        
        if len(query_miewid_cols) < 2 or len(gallery_miewid_cols) < 2:
            logger.info("MiewID embedding columns missing - schema recreation needed")
            return False
        
        logger.info("ReID schema compatibility check passed")
        return True
        
    except Exception as e:
        logger.error(f"Error checking ReID schema compatibility: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    # conn = None
    # cursor = None
    # try:
    #     conn = get_db_connection(DB_CONFIG["dbname"])
    #     if not conn:
    #         return False
    # except Error as e:
    #     logger.error(f"error found in check_reid_schema_compatibility : {e}")

    #     cursor = conn.cursor()
        
def check_schema_match():
    conn = None
    cursor = None
    try:
        conn = get_db_connection(DB_CONFIG["dbname"])
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # First check ReID schema compatibility
        if not check_reid_schema_compatibility():
            return False
        
        type_mappings = {
            'SERIAL': 'INTEGER',
            'VARCHAR': 'CHARACTER VARYING',
            'FLOAT': 'DOUBLE PRECISION',
            'TIMESTAMP': 'TIMESTAMP WITHOUT TIME ZONE',
            'BOOLEAN': 'BOOLEAN',
            'INTEGER': 'INTEGER',
            'JSONB': 'JSONB',
            'VECTOR': 'USER-DEFINED'    # ← added to accept pgvector columns
        }
        
        expected_schema = parse_schema_file()
        logger.info("Checking schema...")
        
        # Check if required tables exist for ReID (new schema)
        reid_tables = [
            "reid_sessions", "uploaded_images", "animal_crops", 
            "gallery_images", "query_images", "matches", "user_feedback",
            "user_gallery_sets"
        ]
        
        for table_name in reid_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (table_name,))
            table_exists = cursor.fetchone()[0]
            if not table_exists:
                logger.warning(f"ReID table {table_name} is missing - will be created")
                return False  # Trigger schema recreation
        
        for table_name, expected_columns in expected_schema.items():
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            existing_columns = cursor.fetchall()
            if not existing_columns:
                logger.warning(f"Table {table_name} missing - will be created")
                return False  # Trigger schema recreation
                
            existing_cols = {col[0]: col[1].upper() for col in existing_columns}
            
            for exp_name, exp_type in expected_columns:
                if exp_name not in existing_cols:
                    logger.warning(f"Missing column {exp_name} in table {table_name} - schema recreation needed")
                    return False  # Trigger schema recreation
                    
                actual_type = existing_cols[exp_name]
                expected_type = type_mappings.get(exp_type, exp_type)
                
                if actual_type != expected_type.upper():
                    logger.warning(f"Type mismatch in {table_name}.{exp_name}: expected {expected_type}, got {actual_type} - schema recreation needed")
                    return False  # Trigger schema recreation
        
        logger.info("Schema validation completed successfully")
        return True

    except Error as e:
        logger.error(f"Error checking schema: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def drop_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = '{DB_CONFIG["dbname"]}'
            AND pid <> pg_backend_pid()
        """)
        
        cursor.execute(f"DROP DATABASE {DB_CONFIG['dbname']}")
        logger.info("Database dropped successfully")
        return True
    except Error as e:
        logger.error(f"Error dropping database: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.debug("\n\nFailed to connect to PostgreSQL server ---directly from get_db_connection()\n\n")
            return False
            
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
        logger.info("Database created successfully")
        return True
    except Error as e:
        logger.error(f"Error creating database: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def populate_classes(conn):
    cursor = None
    try:
        cursor = conn.cursor()
        yaml_path = Path(__file__).parent.parent.parent / "ObjectDetection/models/YOLO/data/wii_aite_2022_testing.yaml"
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            class_names = yaml.safe_load(f).get('names', [])
            
        if not class_names:
            logger.error("No classes found in YOLO config")
            return False

        for idx, name in enumerate(class_names):
            clean_name = name.encode('ascii', 'ignore').decode('ascii')
            cursor.execute(
                "INSERT INTO classes (id, name) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name",
                (idx, clean_name)
            )
        
        conn.commit()
        logger.info(f"Populated {len(class_names)} classes")
        return True
        
    except Exception as e:
        logger.error(f"Error populating classes: {e}")
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()

def create_tables():
    conn = None
    cursor = None
    try:
        conn = get_db_connection(DB_CONFIG["dbname"])
        if not conn:
            return False
            
        cursor = conn.cursor()

        schema_path = Path(__file__).parent.parent / "db/schema.sql"
        with open(schema_path, 'r') as f:
            cursor.execute(f.read())
        
        conn.commit()
        logger.info("Database tables created successfully")

        return populate_classes(conn)
    except Error as e:
        logger.error(f"Error creating tables: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def initialize_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_CONFIG['dbname']}'")
        db_exists = cursor.fetchone() is not None
        
        if db_exists and not check_schema_match():
            logger.info("Schema mismatch detected, recreating database with new ReID schema...")
            cursor.close()
            conn.close()
            return drop_database() and create_database() and create_tables()
        
        if db_exists:
            classes_ok, actual, expected = check_classes_populated()
            if not classes_ok:
                logger.warning(f"Classes mismatch: found {actual}, expected {expected}")
                logger.info("Repopulating classes...")
                cursor.close()
                conn.close()
                conn = get_db_connection(DB_CONFIG["dbname"])
                if not conn:
                    return False
                return populate_classes(conn)
                
        # If database doesn't exist, create it
        if not db_exists:
            cursor.close()
            conn.close()
            return create_database() and create_tables()
            
        return True
            
    except Error as e:
        logger.error(f"Error initializing database: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    success = initialize_database()
    if success:
        logger.info("Database initialization completed successfully")
    else:
        logger.error("Database initialization failed")