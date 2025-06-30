import sys
import json
from pathlib import Path
import argparse
import time
from collections import defaultdict

import torch as T
from ultralytics import YOLO
from PIL import Image
from tqdm import tqdm
import wandb 

from Common.shared_utils import logger 

CURRENT_DIR = Path(__file__).resolve().parent
OBJECT_DETECTION_DIR = CURRENT_DIR.parent 
YOLO_DIR = OBJECT_DETECTION_DIR / "models" / "YOLO"
WEIGHTS_PATH = YOLO_DIR / "runs/train/wii_28_072/weights/best.pt"

for path in [OBJECT_DETECTION_DIR, YOLO_DIR]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

def load_model():
    """Loads the YOLO model and moves it to the appropriate device."""
    logger.info(f"Attempting to load model from: {WEIGHTS_PATH}")
    
    if not WEIGHTS_PATH.exists():
        logger.error(f"Weights file not found at {str(WEIGHTS_PATH)}")
        raise FileNotFoundError(f"Weights file not found at {str(WEIGHTS_PATH)}")

    try:    
        model = YOLO(str(WEIGHTS_PATH))
        device = 'cuda' if T.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {device}")
        
        logger.info("Model loaded successfully")
        logger.info(f"Model class names: {model.names}")
        return model

    except Exception as err:
        logger.error(f"Error loading model: {str(err)}")
        logger.exception(err)
        raise RuntimeError(f"Failed to load YOLO model: {str(err)}") from err

# --- Main Processing ---

def run_batch_inference():
    """Main function to set up and run the batch inference process with W&B tracking."""
    parser = argparse.ArgumentParser(description="Run batch YOLO inference and save results, with W&B tracking.")
    parser.add_argument('--input-dir', type=str, required=True, help='Path to the directory of input images.')
    parser.add_argument('--batch-size', type=int, default=16, help='Batch size for GPU inference.')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='Confidence threshold for detections.')
    parser.add_argument('--num-samples', type=int, default=100, help='Number of sample images to log to W&B Table.')
    parser.add_argument('--no-wandb', action='store_true', help='Disable Weights & Biases logging.')
    args = parser.parse_args()
    
    # --- 1. Initialize W&B Run ---
    run = wandb.init(
        project="YOLO-Batch-Inference", # Your project name
        job_type="inference",
        config={ # Log all hyperparameters and settings
            "model_weights": str(WEIGHTS_PATH),
            "input_directory": args.input_dir,
            "batch_size": args.batch_size,
            "confidence_threshold": args.conf_thres,
            "device": 'cuda' if T.cuda.is_available() else 'cpu',
        },
        mode="disabled" if args.no_wandb else "online",
    )

    # --- 2. Load Model & Prepare Data ---
    model = load_model()
    input_dir = Path(args.input_dir)
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    images_to_process = [p for p in input_dir.rglob('*') if p.suffix.lower() in image_extensions]
    
    if not images_to_process:
        logger.warning("No images found in the input directory. Exiting.")
        wandb.finish()
        return
        
    logger.info(f"Found {len(images_to_process)} images to process.")

    # --- 3. Prepare for W&B Logging ---
    prediction_table = wandb.Table(columns=["image", "detection_count", "predictions_json"])
    
    total_detections = 0
    class_distribution = defaultdict(int)
    confidence_scores = []
    
    # --- 4. Run Inference and Log Data ---
    results_generator = model.predict(
        source=images_to_process, batch=args.batch_size, conf=args.conf_thres, stream=True, verbose=False
    )
    
    start_time = time.time()
    for i, result in enumerate(tqdm(results_generator, total=len(images_to_process), desc="Processing images")):
        image_path = Path(result.path)
        
        num_detections = len(result.boxes)
        total_detections += num_detections
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            class_name = model.names[class_id]
            class_distribution[class_name] += 1
            confidence_scores.append(box.conf[0].item())

        if i < args.num_samples:
            boxes_data = []
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                x1, y1, x2, y2 = box.xywhn[0].tolist() # Using normalized xywh for wandb
                boxes_data.append({
                    "position": {
                        "middle": [x1, y1], # center_x, center_y
                        "width": x2,       # width
                        "height": y2,      # height
                    },
                    "class_id": class_id,
                    "box_caption": f"{model.names[class_id]} ({box.conf[0]:.2f})",
                    "scores": {"confidence": box.conf[0].item()},
                })
            
            wandb_image = wandb.Image(str(image_path), boxes={"predictions": {"box_data": boxes_data, "class_labels": model.names}})
            prediction_table.add_data(wandb_image, num_detections, json.dumps(boxes_data))

    end_time = time.time()
    processing_time = end_time - start_time
    images_per_second = len(images_to_process) / processing_time if processing_time > 0 else 0

    # --- 5. Log Final Summary Metrics and Artifacts to W&B ---
    logger.info("Logging final metrics to Weights & Biases...")
    run.log({
        "summary/total_images_processed": len(images_to_process),
        "summary/total_detections": total_detections,
        "summary/avg_detections_per_image": total_detections / len(images_to_process) if images_to_process else 0,
        "summary/processing_time_seconds": processing_time,
        "summary/images_per_second": images_per_second,
        "charts/class_distribution": wandb.plot.bar(wandb.Table(dataframe=pd.DataFrame(class_distribution.items(), columns=['class', 'count'])), 'class', 'count', title='Class Distribution'),
        "charts/confidence_scores": wandb.Histogram(confidence_scores),
        "samples/predictions": prediction_table
    })

    wandb.finish()
    logger.info("Batch inference complete. W&B run has finished.")

if __name__ == "__main__":
    import pandas as pd
    run_batch_inference()