import os
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
import timm
from typing import List, Tuple, Dict, Any, Optional
from tqdm import tqdm
import logging

class MegaDescriptorWrapper:
    def __init__(self, model_name="hf-hub:BVRA/MegaDescriptor-L-384", device=None):
        self.model_name = model_name
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = None
        
        self._load_model()
    
    def _load_model(self):
        """Load the model and set up image transformations"""
        logging.info(f"Loading model {self.model_name} on {self.device}")
        
        try:
            logging.info("Loading model using timm's huggingface hub integration")
            if self.model_name.startswith("hf-hub:"):
                self.model = timm.create_model(self.model_name, pretrained=True)
            else:
                logging.eror("Megadescriptor is not loading, switching to Resnet50")
                repo_id = self.model_name.replace("hf-hub:", "")
                self.model = timm.create_model(
                    "resnet50", # check
                    pretrained=True,
                    checkpoint_path=f"hf-hub:{repo_id}"
                )
                
            self.model.fc = torch.nn.Identity()  
            
            self.model.to(self.device)
            self.model.eval()
            
            img_size = 384  # MegaDescriptor uses 384x384
                
            self.transform = T.Compose([
                T.Resize((img_size, img_size)),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  # ImageNet stats
                #check the mean and std stats ***************************************88
            ])
            
            logging.info(f"Model loaded successfully. Input size: {img_size}x{img_size}")
            
            # Test the model to check output dimensions                 NO NEED
            test_input = torch.randn(1, 3, img_size, img_size).to(self.device)
            with torch.no_grad():
                test_output = self.model(test_input)
                self.feature_dim = test_output.shape[1]
                logging.info(f"Model output dimension: {self.feature_dim}")
            
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            logging.error("Falling back to random scoring")
            self.model = None
            self.feature_dim = 1536  # Default MegaDescriptor dimension
            raise
    
    def preprocess_image(self, image_path: str) -> torch.Tensor:
        try:
            # Read and convert image to RGB
            image = Image.open(image_path).convert('RGB')
            tensor = self.transform(image)
            return tensor
        except Exception as e:
            logging.error(f"Error preprocessing image {image_path}: {str(e)}")
            return torch.zeros(3, 384, 384)
    
    def extract_features(self, image_paths: List[str], batch_size: int = 16) -> np.ndarray:
        if self.model is None:
            logging.warning("Model not available, returning random features")
            return np.random.randn(len(image_paths), self.feature_dim)  # Use actual model dimensions
            
        self.model.eval()
        
        all_features = []
        
        # Process in batches
        for i in tqdm(range(0, len(image_paths), batch_size), desc="Extracting features"):
            batch_paths = image_paths[i:i+batch_size]
            batch_tensors = [self.preprocess_image(path) for path in batch_paths]
            
            if not batch_tensors:
                continue
                
            batch = torch.stack(batch_tensors).to(self.device)
            
            # Extract features with no gradient computation
            with torch.no_grad():
                features = self.model(batch)
            
            # Move to CPU and convert to numpy
            features_np = features.cpu().numpy()
            
            all_features.append(features_np)
        
        if all_features:
            return np.concatenate(all_features, axis=0)
        else:
            return np.array([])
    
    
    def compute_similarities(self, query_features: np.ndarray, gallery_features: np.ndarray) -> np.ndarray:
        # Normalize features for calculating cosine similarity

        query_norm = query_features / np.linalg.norm(query_features, axis=1, keepdims=True)
        gallery_norm = gallery_features / np.linalg.norm(gallery_features, axis=1, keepdims=True)
        
        similarity_matrix = np.dot(query_norm, gallery_norm.T)
        
        # taking care of scaling from orignal [-1, 1] to [0, 1]
        similarity_matrix = (similarity_matrix + 1) / 2
        
        return similarity_matrix
    
    def get_top_matches(self, similarity_matrix: np.ndarray, gallery_ids: List[str], top_k: int = 10) -> List[List[tuple]]:
        n_queries, n_gallery = similarity_matrix.shape
        all_matches = []
        
        for i in range(n_queries):
            sims = similarity_matrix[i]
            
            # Sort by similarity score (descending)
            sorted_indices = np.argsort(-sims)[:top_k]
            
            matches = [(int(idx), float(sims[idx]), gallery_ids[idx]) for idx in sorted_indices]
            all_matches.append(matches)
            
        return all_matches
