import cv2
import numpy as np
import random
import math
from jenkspy import JenksNaturalBreaks
import torch

def compute_gdsim(patch):
    h, w = patch.shape[:2]
    density_map = np.random.rand(h, w).astype(np.float32)

    def get_partition_counts(density_map, num_parts):
        tensor = torch.from_numpy(density_map)
        height, width = tensor.shape
        parts_per_dim = int(math.sqrt(num_parts))
        part_h = height // parts_per_dim
        part_w = width // parts_per_dim
        parts = []
        for i in range(parts_per_dim):
            for j in range(parts_per_dim):
                part = tensor[i*part_h:(i+1)*part_h, j*part_w:(j+1)*part_w]
                parts.append(torch.sum(part).item())
        return parts

    total = 0
    for L in range(3 + 1):
        num_parts = 4 ** L
        parts = get_partition_counts(density_map, num_parts)
        total += sum(parts)

    return total

def apply_jenks(scores, num_groups):
    jnb = JenksNaturalBreaks(n_classes=num_groups)
    jnb.fit(scores)
    return [jnb.predict([score])[0] for score in scores]

def generate_random_patches(image, num_patches=50, max_area_ratio=0.33):
    h, w, _ = image.shape
    max_area = h * w * max_area_ratio
    boxes = []
    for _ in range(num_patches):
        for _ in range(10):  # Try up to 10 times to get a valid box
            patch_w = random.randint(w // 6, w // 2)
            patch_h = random.randint(h // 6, h // 2)
            if patch_w * patch_h <= max_area:
                x = random.randint(0, w - patch_w)
                y = random.randint(0, h - patch_h)
                boxes.append((x, y, x + patch_w, y + patch_h))
                break
    return boxes

def select_top_patches_from_image(
    image,
    num_total_patches: int = 50,
    num_top_patches: int = 5,
    max_patch_area_ratio: float = 0.33,
    seed: int = 42
) -> list[tuple[int, int, int, int]]:
    """
    Resize the input image to 480×384 and return the top patches in that coordinate space.

    Args:
        image: Input image as a NumPy array.
        num_total_patches: Number of random patches to generate.
        num_top_patches: Number of top-scoring patches to return.
        max_patch_area_ratio: Max area of each patch as a ratio of total image area.
        seed: Random seed for reproducibility.

    Returns:
        A list of (x1, y1, x2, y2) tuples in the 480×384 space.
    """
    # Desired fixed dimensions
    target_w, target_h = 480, 384
    resized = cv2.resize(image, (target_w, target_h))

    # Generate random patches on the resized image
    random.seed(seed)
    boxes = generate_random_patches(resized, num_total_patches, max_patch_area_ratio)

    # Score and group the patches
    scores = [compute_gdsim(resized[y1:y2, x1:x2]) for (x1, y1, x2, y2) in boxes]
    groups = apply_jenks(scores, num_top_patches)

    # Combine and sort by score descending
    patch_info = sorted(zip(boxes, scores, groups), key=lambda item: item[1], reverse=True)

    # Select one patch per group until we have the top patches
    selected = []
    used = set()
    for (x1, y1, x2, y2), score, grp in patch_info:
        if grp not in used:
            selected.append((x1, y1, x2, y2))
            used.add(grp)
        if len(selected) == num_top_patches:
            break

    return selected

