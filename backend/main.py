from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ObjectDetection.inference.inference import load_model

from Common.db.initialize_database import initialize_database
from Common.shared_utils import logger, UPLOAD_DIR
from Common.api.images import router as common_images_router
from Common.api.upload import router as upload_router
from Common.api.download import router as download_router
from Common.api.auth import router as auth_router
from Common.api.admin import router as admin_router

from ObjectDetection.api.bounding_boxes import router as bounding_boxes_router
from ObjectDetection.api.classes import router as classes_router
from ObjectDetection.api.cleanup import router as cleanup_router
from ObjectDetection.api.utils.scheduler import check_and_update_rankings

from BirdCount.api.annotations import router as annotations_router
from BirdCount.api.model_api import router as model_api_router
from BirdCount.api.active_learning import router as active_learning_router

from ReID.api.reid import router as reid_router
from ReID.auto_truncate_utils import cleanup_non_consented_reid_data

import torch
from transformers import CLIPModel, CLIPProcessor

load_dotenv()

app = FastAPI()
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3012",
    "http://127.0.0.1:3012"
]

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = Response("Internal server error", status_code=500)
        
        try:
            # Handle preflight (OPTIONS) requests
            if request.method == "OPTIONS":
                response = Response(status_code=200)
            else:
                response = await call_next(request)
        except Exception as e:
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        
        origin = request.headers.get('origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Vary'] = 'Origin'  # Ensures caches differentiate based on Origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Expose-Headers'] = '*' 
        
        return response

app.add_middleware(CustomCORSMiddleware)

@app.on_event("startup")
async def startup_event():
    logger.info("Checking database configuration...")
    try:
        if not initialize_database():
            raise Exception("Failed to initialize database")
        logger.info("Database configuration verified successfully")
        
        app.state.model = load_model()
        logger.info("YOLO model loaded successfully")
        
        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        app.state.clip_model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32"
        ).to(DEVICE)
        app.state.clip_processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32"
        )
        logger.info("CLIP model and processor loaded successfully")
        
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(check_and_update_rankings, 'interval', minutes=1)
        
        scheduler.add_job(
            func=cleanup_non_consented_reid_data,
            trigger='interval', 
            hours=1,
            id='reid_cleanup',
            name='Cleanup non-consented ReID data'
        )
        
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Background scheduler started with ReID cleanup job")
        logger.info("APScheduler started with FastAPI startup event.")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise RuntimeError("Could not initialize application")


#Common
app.include_router(upload_router)
app.include_router(download_router)
app.include_router(common_images_router)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router)

#Object Detection
app.include_router(bounding_boxes_router)
app.include_router(classes_router)
app.include_router(cleanup_router)


#BIRD COUNT
app.include_router(annotations_router)
app.include_router(model_api_router)
app.include_router(active_learning_router)

#RE ID
app.include_router(reid_router, prefix="/reid")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug")