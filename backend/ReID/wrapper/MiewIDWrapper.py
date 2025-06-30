import os
import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image
from transformers import AutoModel
from typing import List, Tuple, Dict, Any, Optional
from tqdm import tqdm
import logging

class MiewIDWrapper:
    def __init__(self, model_name="conservationxlabs/miewid-msv3", device=None):
        self.model_name = model_name
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = None
        
        self._load_model()
    
    def _load_model(self):
        """Load the MiewID model and set up image transformations"""
        logging.info(f"Loading MiewID model {self.model_name} on {self.device}")
        
        try:
            # Load MiewID model using transformers AutoModel
            self.model = AutoModel.from_pretrained(self.model_name, trust_remote_code=True)
            self.model.to(self.device)
            self.model.eval()
            
            # MiewID uses 440x440 input size
            img_size = 440
                
            self.transform = transforms.Compose([
                transforms.Resize((img_size, img_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  # ImageNet stats
            ])
            
            logging.info(f"MiewID model loaded successfully. Input size: {img_size}x{img_size}")
            
            # Test the model to check output dimensions
            test_input = torch.randn(1, 3, img_size, img_size).to(self.device)
            with torch.no_grad():
                test_output = self.model(test_input)
                self.feature_dim = test_output.shape[1]
                logging.info(f"MiewID model output dimension: {self.feature_dim}")
            
        except Exception as e:
            logging.error(f"Error loading MiewID model: {e}")
            logging.error("MiewID model loading failed - no fallback available")
            self.model = None
            self.feature_dim = 2152  # Expected MiewID dimension
            raise
    
    def preprocess_image(self, image_path: str) -> torch.Tensor:
        """Preprocess a single image for MiewID model input"""
        try:
            # Read and convert image to RGB
            image = Image.open(image_path).convert('RGB')
            tensor = self.transform(image)
            return tensor
        except Exception as e:
            logging.error(f"Error preprocessing image {image_path}: {str(e)}")
            return torch.zeros(3, 440, 440)
    
    def extract_features(self, image_paths: List[str], batch_size: int = 16) -> np.ndarray:
        """Extract features from a list of image paths using batch processing"""
        if self.model is None:
            logging.error("MiewID model not available")
            raise RuntimeError("MiewID model failed to load")
            
        self.model.eval()
        
        all_features = []
        
        # Process in batches
        for i in tqdm(range(0, len(image_paths), batch_size), desc="Extracting MiewID features"):
            batch_paths = image_paths[i:i+batch_size]
            batch_tensors = [self.preprocess_image(path) for path in batch_paths]
            
            if not batch_tensors:
                continue
                
            batch = torch.stack(batch_tensors).to(self.device)
            
            # Extract features with no gradient computation
            with torch.no_grad():
                features = self.model(batch)  # Expected shape: [batch_size, 2152]
            
            # Move to CPU and convert to numpy
            features_np = features.cpu().numpy()
            
            all_features.append(features_np)
        
        if all_features:
            return np.concatenate(all_features, axis=0)
        else:
            return np.array([])
    
    def compute_similarities(self, query_features: np.ndarray, gallery_features: np.ndarray) -> np.ndarray:
        """Compute cosine similarities between query and gallery features"""
        # Normalize features for calculating cosine similarity
        query_norm = query_features / np.linalg.norm(query_features, axis=1, keepdims=True)
        gallery_norm = gallery_features / np.linalg.norm(gallery_features, axis=1, keepdims=True)
        
        similarity_matrix = np.dot(query_norm, gallery_norm.T)
        
        # Scale from original [-1, 1] to [0, 1]
        similarity_matrix = (similarity_matrix + 1) / 2
        
        return similarity_matrix
    
    def get_top_matches(self, similarity_matrix: np.ndarray, gallery_ids: List[str], top_k: int = 10) -> List[List[tuple]]:
        """Get top k matches for each query based on similarity scores"""
        n_queries, n_gallery = similarity_matrix.shape
        all_matches = []
        
        for i in range(n_queries):
            sims = similarity_matrix[i]
            
            # Sort by similarity score (descending)
            sorted_indices = np.argsort(-sims)[:top_k]
            
            matches = [(int(idx), float(sims[idx]), gallery_ids[idx]) for idx in sorted_indices]
            all_matches.append(matches)
            
        return all_matches