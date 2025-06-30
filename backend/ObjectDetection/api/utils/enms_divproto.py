import torch
import torch.nn.functional as F
from collections import defaultdict, Counter

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../.."))
sys.path.append(project_root)

backend_dir = os.path.join(project_root, "backend")
sys.path.append(backend_dir)

from ObjectDetection.inference.inference import load_model
from Common.shared_utils import get_db_connection, MODEL_TYPE_OBJECT_DETECTION, logger

from PIL import Image
from torchvision import transforms
import torch as T

# parameters for the algorithm (taken from the paper)
t_enms = 0.5    # threshold for instance-level redundancy removal
t_intra = 0.7   # threshold for intra-class diversity
t_inter = 0.3   # threshold for inter-class diversity
alpha = 0.5     # proportion of minority classes
beta = 0.75     # budget proportion for minority classes

def calculate_entropy(p):
    return -p * torch.log(p) - (1 - p) * torch.log(1 - p)

def entropy_nms(pred_classes, confidences, features):
    entropies = calculate_entropy(confidences)
    available = list(range(len(pred_classes)))
    selected = []
    total_entropy = 0.0

    while available:
        idx = max(available, key=lambda i: entropies[i])
        available.remove(idx)
        selected.append(idx)
        total_entropy += entropies[idx].item()
        current_class = pred_classes[idx]
        # get rid of boxes from the same class that are too similar
        remove_ids = []
        for i in available:
            if pred_classes[i] == current_class:
                sim = F.cosine_similarity(features[idx].unsqueeze(0), features[i].unsqueeze(0)).item()
                if sim > t_enms:
                    remove_ids.append(i)
        for i in remove_ids:
            if i in available:
                available.remove(i)
    return total_entropy, selected

def create_prototype(features, pred_classes, entropies, num_classes):
    prototypes = {}
    for cls in set(pred_classes):
        # this filtering is equivalent to applying the indicator function 1(c, ci,k) from the paper
        # which is 1 only when the predicted class ci,k matches the class c we're creating a prototype for
        indices = [i for i, x in enumerate(pred_classes) if x == cls]
        if indices:
            cls_features = features[indices]
            cls_entropies = entropies[indices]
            # this weighted sum implements Equation (3) from the paper
            # the filtering above ensures we only include features where the indicator function would be 1
            weighted_sum = (cls_features * cls_entropies.unsqueeze(1)).sum(dim=0)
            prototypes[cls] = weighted_sum / cls_entropies.sum()
    return prototypes

def measure_intra_class_diversity(candidate_proto, selected_protos):
    if not selected_protos:
        return 0.0
    
    # initialize with positive infinity to find the minimum
    min_max_similarity = float('inf')
    
    for cls, proto in candidate_proto.items():
        # for each class, find the maximum similarity across all selected prototypes
        max_sim_for_class = 0.0
        
        # find the maximum similarity for this class across all selected prototypes
        for sel_proto in selected_protos:
            if cls in sel_proto:
                sim = F.cosine_similarity(proto.unsqueeze(0), sel_proto[cls].unsqueeze(0)).item()
                max_sim_for_class = max(max_sim_for_class, sim)
        
        # if we found any similarity for this class, update the min_max_similarity
        if max_sim_for_class > 0:
            min_max_similarity = min(min_max_similarity, max_sim_for_class)
    
    # if no classes matched (min_max_similarity still infinity), return 0
    if min_max_similarity == float('inf'):
        return 0.0
    
    return min_max_similarity

def get_minority_classes(labeled_set, num_classes, budget):
    counts = defaultdict(int)
    for record in labeled_set:
        for cls, cnt in record.get('class_counts', {}).items():
            counts[cls] += cnt
    sorted_classes = sorted(range(num_classes), key=lambda c: counts.get(c, 0))
    num_minority = int(alpha * num_classes)
    minority_classes = sorted_classes[:num_minority]
    quota = int(beta * budget / (alpha * num_classes))
    return minority_classes, {c: quota for c in minority_classes}, num_minority

def measure_inter_class_diversity(image_data, minority_classes):
    max_conf = 0
    present = {}
    
    for cls in minority_classes:
        # find all confidence scores for this class in the image
        scores = [score for c, score in zip(image_data['pred_classes'], image_data['confidence'].tolist()) 
                  if c == cls]
        
        # if this minority class appears in the image
        if scores:
            # get the maximum confidence for this class (p(i,c) in the paper)
            high = max(scores)
            # only consider it "present" if above threshold
            if high > t_inter:
                present[cls] = high
                # update the overall maximum across all minority classes (M_p in the paper)
                max_conf = max(max_conf, high)    
    return present, max_conf

def select_samples(unlabeled, labeled, budget, num_classes):
    entropy_list = []
    prototypes_list = []
    
    # step 1: Calculate entropy and prototypes for each image
    for i, data in enumerate(unlabeled):
        features = data['features']
        classes = data['pred_classes']
        confidences = data['confidence']
        tot_entropy, selected_ids = entropy_nms(classes, confidences, features)
        sel_features = features[selected_ids]
        sel_classes = [classes[j] for j in selected_ids]
        sel_entropies = calculate_entropy(confidences[selected_ids])
        protos = create_prototype(sel_features, sel_classes, sel_entropies, num_classes)
        entropy_list.append((i, tot_entropy))
        prototypes_list.append(protos)
    
    # sort by entropy (descending order) as per the paper
    entropy_list.sort(key=lambda x: x[1], reverse=True)
    
    # step 2: calculate quotas for minority classes
    minority_classes, quotas, num_minority_to_select = get_minority_classes(labeled, num_classes, budget)
    remaining = set(minority_classes)
    selected_indices = []
    selected_prototypes = []
    
    # step 3-10: select images that satisfy diversity criteria
    for idx, _ in entropy_list:
        if len(selected_indices) >= budget:
            break
            
        data = unlabeled[idx]
        protos = prototypes_list[idx]
        
        # calculate intra-class diversity (M_g in the paper)
        intra_div = measure_intra_class_diversity(protos, selected_prototypes)
        
        # calculate inter-class diversity (M_p in the paper)
        present, max_conf = measure_inter_class_diversity(data, list(remaining))
        
        # step 5: check if image satisfies both diversity criteria
        if intra_div < t_intra and max_conf > 0:  # max_conf > 0 means at least one minority class is present with conf > t_inter
            selected_indices.append(idx)
            selected_prototypes.append(protos)
            
            # steps 7-10: update quotas and minority class set
            for cls in present:
                quotas[cls] -= 1
                if quotas[cls] <= 0 and cls in remaining:
                    remaining.discard(cls)
                    num_minority_to_select -= 1  # update count of remaining minority classes
    
    # Step 11: fill remaining slots by entropy ranking
    if len(selected_indices) < budget:
        for idx, _ in entropy_list:
            if idx not in selected_indices:
                selected_indices.append(idx)
                if len(selected_indices) >= budget:
                    break

    return selected_indices[:budget]


def extract_features(filepath, num_boxes, feature_extractor):
    img = Image.open(filepath).convert("RGB")
    preprocess = transforms.Compose([
        transforms.Resize((640, 640)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std =[0.229, 0.224, 0.225]),
    ])
    img_tensor = preprocess(img).unsqueeze(0)
    with T.no_grad():
        features = feature_extractor(img_tensor)
    features = features.flatten(1)
    if features.dim() == 1:
        features = features.unsqueeze(0)
    return features.repeat(num_boxes, 1)


def fetch_unlabeled_data():
    data_list = []
    
    yolo_model = load_model()
    feature_extractor = torch.nn.Sequential(*(list(yolo_model.model.children())[:-1]))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, filename, filepath, width, height
                    FROM images
                    WHERE model_type = %s
                """, (MODEL_TYPE_OBJECT_DETECTION,))
                images = cur.fetchall()
                for img in images:
                    image_id, _, filepath, _, _ = img
                    cur.execute("""
                        SELECT class_id, confidence
                        FROM model_predicted_boxes
                        WHERE image_id = %s
                    """, (image_id,))
                    boxes = cur.fetchall()
                    if not boxes:
                        continue
                    classes = [row[0] for row in boxes]
                    confidences = [row[1] for row in boxes]
                    features = extract_features(filepath, len(boxes), feature_extractor)
                    class_count = dict(Counter(classes))
                    data_list.append({
                        'id': image_id,
                        'pred_classes': classes,
                        'confidence': torch.tensor(confidences),
                        'features': features,
                        'class_counts': class_count
                    })
    except Exception as e:
        logger.error(f"Error fetching unlabeled data: {e}")
    return data_list


def update_active_learning_rankings():
    try:
        unlabeled_data = fetch_unlabeled_data()
        labeled_data = []
        
        if not unlabeled_data:
            logger.info("No unlabeled data available for ranking")
            return
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM classes")
                    num_classes = cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting class count: {e}")
            num_classes = 98
        
        budget = len(unlabeled_data)
        ranked_indices = select_samples(unlabeled_data, labeled_data, budget, num_classes)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                algorithm_type = "enms_diversity"
                cur.execute("""
                    DELETE FROM active_learning_rankings 
                    WHERE algorithm_type = %s
                """, (algorithm_type,))
                
                for rank, idx in enumerate(ranked_indices):
                    image_id = unlabeled_data[idx]['id']
                    cur.execute("""
                        INSERT INTO active_learning_rankings 
                        (image_id, algorithm_type, ranking_score) 
                        VALUES (%s, %s, %s)
                    """, (image_id, algorithm_type, rank)
                    )
                conn.commit()
                logger.info(f"Updated rankings for {len(ranked_indices)} images using algorithm '{algorithm_type}'")
    
    except Exception as e:
        logger.error(f"Error updating active learning rankings: {e}")

if __name__ == "__main__":
    update_active_learning_rankings()