import sys
from pathlib import Path
import argparse
import shutil

import torch as T
from ultralytics import YOLO
from PIL import Image

from Common.shared_utils import logger

CURRENT_DIR = Path(__file__).resolve().parent
OBJECT_DETECTION_DIR = CURRENT_DIR.parent
YOLO_DIR = OBJECT_DETECTION_DIR / "models" / "YOLO"
# WEIGHTS_PATH = YOLO_DIR / "runs/train/wii_28_072/weights/best.pt"
WEIGHTS_PATH = YOLO_DIR / "runs/train/wii_28_072/weights/bestx.pt"

for path in [OBJECT_DETECTION_DIR, YOLO_DIR]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

from models.YOLO.detect import run

def load_model():
    logger.debug(f"Loading model from path: {WEIGHTS_PATH}")
    
    if not WEIGHTS_PATH.exists():
        logger.error(f"Weights file not found at {str(WEIGHTS_PATH)}")
        raise FileNotFoundError(f"Weights file not found at {str(WEIGHTS_PATH)}")

    try:    
        model = YOLO(str(WEIGHTS_PATH))
        
        device = 'cuda' if T.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {device}")
        
        model = model.to(device)
        model.eval()
        
        logger.info("Model loaded successfully")
        return model

    except Exception as err:
        logger.error(f"Error loading model: {str(err)}")
        logger.exception(err)
        raise RuntimeError(f"Failed to load YOLOv5 model: {str(err)}")

def run_inference(image_path, model):
    logger.debug(f"Starting inference on image: {image_path}")
    
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        logger.debug(f"Original image dimensions: {img_width}x{img_height}")

    try:
        results = model.predict(source=image_path,
            save_txt=True,
            save_conf=True,
            exist_ok=True,
            save=False,
            project=str(YOLO_DIR / "runs/detect"),
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = box.conf[0].item()
                class_id = int(box.cls[0].item())
                width = x2 - x1
                height = y2 - y1
                detection = {
                    "x": (x1 + width/2),
                    "y": (y1 + height/2),
                    "width": width,
                    "height": height,
                    "confidence": confidence,
                    "class_id": class_id
                }
                detections.append(detection)

        
        logger.info(f"Processed {len(detections)} detections")
        return detections
            
    except Exception as err:
        logger.error(f"Inference failed: {str(err)}")
        logger.exception(err)
        raise RuntimeError(f"Inference failed: {str(err)}")

def setup_directories(storage_path):
    paths = {
        'raw': storage_path / "raw_images",
        'processed': storage_path / "processed_images",
        'annotations': storage_path / "annotations"
    }
    
    for path in [storage_path, *paths.values()]:
        path.mkdir(parents=True, exist_ok=True)
        
    return paths

def main():
    parser = argparse.ArgumentParser(description="Run YOLOv5 inference on an image")
    parser.add_argument('--image', type=str, required=True, help='Path to input image')
    parser.add_argument('--save', action='store_true', help='Save the output image with predictions')
    parser.add_argument('--show', action='store_true', help='Display the output image with predictions')
    args = parser.parse_args()

    paths = setup_directories(Path("images"))
    raw_image_path = paths['raw'] / Path(args.image).name
    shutil.copy2(args.image, raw_image_path)
    
    model = load_model()
    
    if args.save or args.show:
        results = model.predict(
            source=args.image,
            project=paths['processed'],
            name='',
            save_txt=True,
            save_conf=True,
            exist_ok=True,
            save=args.save,  
            show=args.show
        )
        logger.info(f"Results saved to {paths['processed']}")
    else:
        detections = run_inference(args.image, model)
        print(f"Found {len(detections)} objects in the image")
        for i, det in enumerate(detections):
            print(f"  {i+1}: Class {det['class_id']} at ({det['x']}, {det['y']}) with confidence {det['confidence']:.2f}")

if __name__ == "__main__":
    main()