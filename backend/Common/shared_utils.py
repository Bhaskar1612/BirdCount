import os
import psycopg2
from psycopg2.extras import DictCursor
from fastapi import Request, HTTPException
import logging
from dotenv import load_dotenv
from logging.config import dictConfig

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
        },
    },
    "loggers": {
        "wildlife": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("wildlife")
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv('DB_NAME', 'wildlife_monitoring'),
    "user": os.getenv('DB_USER', 'postgres'),
    "password": os.getenv('DB_PASSWORD', 'admin'),
    "host": os.getenv('DB_HOST', 'localhost'),
    "port": os.getenv('DB_PORT', '5432')
}

# Define upload directory with absolute path for better reliability
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, os.getenv('UPLOAD_DIR', 'uploads'))

# Create upload directory and subdirectories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "reid"), exist_ok=True)

MODEL_TYPE_OBJECT_DETECTION = 1
MODEL_TYPE_BIRD_COUNT = 2

def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=DictCursor)
    return conn

def get_database_url(db_name=None):
    """Get database URL for SQLAlchemy"""
    config = DB_CONFIG.copy()
    if db_name:
        config["dbname"] = db_name
    
    return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['dbname']}"

def raise_not_found(detail: str = "Resource not found"):
    raise HTTPException(status_code=404, detail=detail)

def raise_unauthorized(detail: str = "Unauthorized"):
    raise HTTPException(status_code=401, detail=detail)

async def get_model(request: Request):
    return request.app.state.model