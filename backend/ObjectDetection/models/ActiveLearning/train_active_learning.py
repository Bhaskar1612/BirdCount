import os
import shutil
from pathlib import Path
from psycopg2.extras import DictCursor
import yaml
import sys

ROOT_DIR = Path(__file__).resolve().parents[4]
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / 'backend'))

from Common.shared_utils import logger, get_db_connection
from ObjectDetection.models.YOLO.train import train, parse_opt
from ObjectDetection.models.YOLO.utils.callbacks import Callbacks
from ObjectDetection.models.YOLO.utils.torch_utils import select_device


def train_with_active_learning_data():

    active_learning_dir = ROOT_DIR / 'backend' / 'ObjectDetection' / 'models' / 'ActiveLearning'
    image_dir = active_learning_dir / 'images'
    labels_dir = active_learning_dir / 'labels'
    data_yaml_path = active_learning_dir / 'active_learning_data.yaml'
    weights_path = ROOT_DIR / 'backend' / 'ObjectDetection' / 'models' / 'YOLO' / 'runs' / 'train' / 'wii_28_072' / 'weights' / 'best.pt'
    yaml_path = ROOT_DIR / 'backend' / 'ObjectDetection' / 'models' / 'YOLO' / 'data' / 'wii_aite_2022_testing.yaml'
    hyp_path = ROOT_DIR / 'backend' / 'ObjectDetection' / 'models' / 'YOLO' / 'data' / 'hyps' / 'hyp.scratch-low.yaml'

    logger.info(f"ROOT_DIR: {ROOT_DIR}")
    logger.info(f"YAML path: {yaml_path}")

    image_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                logger.info("Reading class names from YAML file...")
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    class_names = data['names']
                    num_classes = len(class_names)
                logger.info(f"Number of classes: {num_classes}")
                logger.info(f"Class names: {class_names}")

                logger.info("Fetching active learning data from the database...")
                cur.execute("""
                    SELECT
                        alb.image_id,
                        alb.x AS box_x,
                        alb.y AS box_y,
                        alb.width AS box_width,
                        alb.height AS box_height,
                        alb.class_id,
                        i.filepath,
                        i.width AS image_width,
                        i.height AS image_height
                    FROM
                        active_learning_boxes alb
                    JOIN
                        images i ON alb.image_id = i.id;
                """)
                boxes = cur.fetchall()

                if not boxes:
                    logger.info("No new active learning data available.")
                    return

                logger.info(f"Fetched {len(boxes)} bounding boxes from active_learning_boxes.")

                image_paths = {}
                for box in boxes:
                    image_id = box['image_id']
                    image_path = box['filepath']
                    image_width = box['image_width']
                    image_height = box['image_height']
                    box_x = box['box_x']
                    box_y = box['box_y']
                    box_width = box['box_width']
                    box_height = box['box_height']
                    class_id = box['class_id']

                    label_file_name = f"{image_id}.txt"
                    label_file_path = labels_dir / label_file_name

                    x_center_norm = box_x / image_width
                    y_center_norm = box_y / image_height
                    width_norm = box_width / image_width
                    height_norm = box_height / image_height

                    with open(label_file_path, 'a') as lf:
                        lf.write(f"{class_id} {x_center_norm} {y_center_norm} {width_norm} {height_norm}\n")

                    image_paths[image_id] = image_path

                logger.info("Copying images to training directory...")
                for image_id, image_path in image_paths.items():
                    image_name = os.path.basename(image_path)
                    label_file_name = f"{Path(image_name).stem}.txt"
                    label_file_path = labels_dir / label_file_name
                    destination_path = image_dir / image_name
                    
                    with open(label_file_path, 'a') as lf:
                        lf.write(f"{class_id} {x_center_norm} {y_center_norm} {width_norm} {height_norm}\n")

                    corrected_image_path = os.path.join(ROOT_DIR, "backend", image_path)

                    if os.path.exists(corrected_image_path):
                        shutil.copy(corrected_image_path, str(destination_path))
                        logger.info(f"Copied {image_name} to {image_dir}")
                    else:
                        logger.error(f"Image file not found: {corrected_image_path}")
                        logger.error(f"Current working directory: {os.getcwd()}")
                        logger.error(f"Full image path: {os.path.abspath(corrected_image_path)}")
                        continue

                logger.info("Generating YOLO data YAML file...")
                with open(data_yaml_path, 'w') as f:
                    f.write(f"train: {image_dir}\n")
                    f.write(f"val: {image_dir}\n")
                    f.write(f"nc: {num_classes}\n")
                    f.write(f"names: {class_names}\n")

                logger.info("Starting YOLO training...")
                logger.info(f"Weights path: {weights_path}")
                before_time = os.path.getmtime(weights_path)
                logger.info(f"Weights modification time BEFORE training: {before_time}")

                opt = parse_opt(known=True)
                opt.weights = str(weights_path)
                opt.data = str(data_yaml_path)
                opt.hyp = str(hyp_path)
                opt.epochs = 10
                opt.project = str(active_learning_dir)
                opt.name = 'active_learning_exp'
                opt.exist_ok = True
                opt.save_dir = opt.project + '/' + opt.name

                device = select_device(opt.device)

                train(opt.hyp, opt, device, Callbacks())

                logger.info("YOLO training completed.")
                after_time = os.path.getmtime(weights_path)
                logger.info(f"Weights modification time AFTER training: {after_time}")
                logger.info("Active learning training complete.")

    except Exception as e:
        logger.error(f"Error during active learning training: {e}")


if __name__ == "__main__":
    train_with_active_learning_data()