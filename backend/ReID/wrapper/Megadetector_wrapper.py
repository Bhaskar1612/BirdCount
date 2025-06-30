import os
import torch
import numpy as np
from PIL import Image
from PytorchWildlife.models import detection as pw_detection
from PytorchWildlife import utils as pw_utils
from typing import List, Tuple, Dict, Any, Optional

class MegaDetectorWrapper:
    def __init__(self, model_version: str = "MDV6-yolov10-e", device: str = None, confidence_threshold: float = 0.1):
        self.model_version = model_version
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.confidence_threshold = confidence_threshold
        self.model = self.load_model()
        
    def load_model(self):
        detection_model = pw_detection.MegaDetectorV6(device=self.device, pretrained=True, version=self.model_version)
        return detection_model
        
    def detect_animals(self, image_path: str) -> List[Dict[str, Any]]:
        results = self.model.single_image_detection(image_path)     # removed the confidence threshold argument
        
        # Handle empty results
        if not results or 'detections' not in results:
            return []
            
        detections = results['detections']
        if not hasattr(detections, 'xyxy') or len(detections.xyxy) == 0:
            return []
        
        box_coords = detections.xyxy
        confidence_scores = detections.confidence       #removed .cpu(), 
        labels = detections.class_id  # Fixed typo: 'lables' -> 'class_id'
        
        category_map = {0: 'animal', 1: 'person', 2: 'vehicle'}
        formatted_results = []
        
        for box, conf, label in zip(box_coords, confidence_scores, labels):
            x1, y1, x2, y2 = box
            formatted_results.append({
                'bbox': [float(x1), float(y1), float(x2-x1), float(y2-y1)],  # x,y,w,h
                'confidence': float(conf),
                'category': category_map.get(int(label), 'unknown')
            })
            
        return formatted_results
            
    def detect_animals_batch(self, folder_path: str, batch_size: int = 16) -> Dict[str, List[Dict[str, Any]]]:
        results = self.model.batch_image_detection(folder_path, batch_size=batch_size)                  # removed confidence threshold from here
        
        formatted_results = {}
        
        for image_path, detections in results.items():
            if not detections or 'detections' not in detections:
                formatted_results[image_path] = []
                continue
                
            det = detections['detections']
            if not hasattr(det, 'xyxy') or len(det.xyxy) == 0:
                formatted_results[image_path] = []
                continue
                
            box_coords = det.xyxy
            confidence_scores = det.confidence
            labels = det.class_id
            
            category_map = {0: 'animal', 1: 'person', 2: 'vehicle'}
            image_results = []
            
            for box, conf, label in zip(box_coords, confidence_scores, labels):
                x1, y1, x2, y2 = box
                image_results.append({
                    'bbox': [float(x1), float(y1), float(x2-x1), float(y2-y1)],
                    'confidence': float(conf),
                    'category': category_map.get(int(label), 'unknown')
                })
                
            formatted_results[image_path] = image_results
            
        return formatted_results
        
    def filter_detections(self, detections: List[Dict], min_confidence: float = None, 
                         categories: List[str] = ["animal"]) -> List[Dict]:
        if min_confidence is None:
            min_confidence = self.confidence_threshold
            
        filtered = []
        for det in detections:
            if det['category'] in categories and det['confidence'] >= min_confidence:
                filtered.append(det)
                
        return filtered
           
    def get_crop_coordinates(self, bbox: List[float], image_shape: tuple, 
                           padding_factor: float = 0.1) -> Dict[str, int]:
        x, y, width, height = bbox
        img_height, img_width = image_shape
        
        # Add padding
        pad_w = width * padding_factor
        pad_h = height * padding_factor
        
        # Calculate padded coordinates
        x_min = max(0, int(x - pad_w))
        y_min = max(0, int(y - pad_h))
        x_max = min(img_width, int(x + width + pad_w))
        y_max = min(img_height, int(y + height + pad_h))
        
        return {
            'x_min': x_min,
            'y_min': y_min,
            'x_max': x_max,
            'y_max': y_max
        }
        
    def visualize_detections(self, image_path: str, detections: List[Dict], 
                            output_path: str = None) -> np.ndarray:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # Simple visualization without cv2 dependency
        # In production, you'd use cv2.rectangle and cv2.putText
        
        if output_path:
            # Would save annotated image here
            pass
            
        return img_array