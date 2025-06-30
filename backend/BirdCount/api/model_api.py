import io
from fastapi import APIRouter, UploadFile, File, Response, Depends
from PIL import Image
from torchvision import transforms

from Common.api.auth import get_current_user

import BirdCount.model_files.demomodified as demo

import math

import numpy as np
import torch
from scipy import ndimage
from PIL import Image

router = APIRouter()

def helper_get_heatmap(file: UploadFile = File(...)):
    image = Image.open(file.file)
    if image.format == "PNG":
        # Convert to RGB (as PNG can have alpha channel)
        image = image.convert("RGB")

        # Save to a bytes buffer in JPEG format
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Re-open the image from the buffer
        image = Image.open(buffer)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return heatmap_file

@router.post("/model_heatmap/")
async def predict(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
):
    heatmap_file=helper_get_heatmap(file)
    to_pil = transforms.ToPILImage()
    image = to_pil(heatmap_file)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type="image/png")

def helper_get_gridmap(file: UploadFile = File(...)):
    image = Image.open(file.file)
    if image.format == "PNG":
        # Convert to RGB (as PNG can have alpha channel)
        image = image.convert("RGB")

        # Save to a bytes buffer in JPEG format
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Re-open the image from the buffer
        image = Image.open(buffer)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return subgridcounts_error

@router.post("/model_gridmap/")
async def predict(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
):
    gridmap=helper_get_gridmap(file)
    return gridmap

def helper_get_count(file: UploadFile = File(...)):
    image = Image.open(file.file)
    if image.format == "PNG":
        # Convert to RGB (as PNG can have alpha channel)
        image = image.convert("RGB")

        # Save to a bytes buffer in JPEG format
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Re-open the image from the buffer
        image = Image.open(buffer)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return pred_cnt_flt

@router.post("/model_count/")
async def predict(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
):
    count=helper_get_count(file)
    return count

def helper_get_cluster1(file: UploadFile = File(...)):
    image = Image.open(file.file)
    if image.format == "PNG":
        # Convert to RGB (as PNG can have alpha channel)
        image = image.convert("RGB")

        # Save to a bytes buffer in JPEG format
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Re-open the image from the buffer
        image = Image.open(buffer)
    original_tensor_size = (480, 384)  # Tensor size (width, height)
    target_image_size = image.size  # Actual image size (width, height)
    print(image.size)

    # Replace the demo logic with the real function generating cluster centers
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions, subgrid_counts, pred_cnt_flt, subgridcounts_error = demo.run_demo_image_nomongo(image)
    return cluster_centers


@router.post("/model_cluster/")
async def predict(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),                  
):
    cluster_centers=helper_get_cluster1(file)
    return cluster_centers



def split_image(image, grid_size=(3, 3)):
    """Splits an image into a 3×3 grid without losing any pixels."""
    width, height = image.size
    grid_w, grid_h = grid_size

    sub_images = []
    sub_coords = []  # Store (x, y) positions for reassembling

    # Compute **exact** sub-image dimensions
    sub_w = round(width / grid_w)
    sub_h = round(height / grid_h)

    for row in range(grid_h):
        for col in range(grid_w):
            left = col * sub_w
            upper = row * sub_h
            right = min(left + sub_w, width)  # Ensure it doesn't exceed original image
            lower = min(upper + sub_h, height)

            sub_image = image.crop((left, upper, right, lower))
            sub_images.append(sub_image)
            sub_coords.append((left, upper))  # Store original position

    return sub_images, sub_coords, (width, height)

@router.post("/split-image/")
async def split_and_return_images(file: UploadFile = File(...)):
    """Splits an image into a 3×3 grid and returns them as separate image responses."""
    image = Image.open(file.file)

    sub_images, sub_coords, _ = split_image(image)
    for sub_image in sub_images:
        print(sub_image.size)
    

    count, elapsed_time, heatmap_tensor, cluster_centers, _, _, _, _ = demo.run_demo_image_nomongo(sub_images[0])
    
    to_pil = transforms.ToPILImage()
    image = to_pil(heatmap_tensor)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type="image/png")
        


def merge_heatmaps(heatmaps, grid_size=(3, 3)):
    """Merges heatmaps from sub-images back into a single large heatmap."""
    
    # Since each heatmap is 480x384, compute final image size
    sub_w, sub_h = 480, 384
    full_w, full_h = sub_w * grid_size[0], sub_h * grid_size[1]

    full_heatmap = Image.new("RGB", (full_w, full_h))  # Create blank canvas

    for idx, heatmap in enumerate(heatmaps):
        row, col = divmod(idx, grid_size[0])  # Get row, column position
        x, y = col * sub_w, row * sub_h  # Correct x, y position
        
        full_heatmap.paste(heatmap, (x, y))  # Paste correctly

    return full_heatmap


def scale_cluster_points(cluster_centers, grid_size=(3, 3)):
    """Scales cluster points back to full image coordinates based on fixed 480x384 sub-image sizes."""
    
    sub_w, sub_h = 480, 384  # Each split heatmap size
    scaled_points = []

    for idx, centers in enumerate(cluster_centers):
        row, col = divmod(idx, grid_size[0])  # Compute row, col in grid
        x_offset, y_offset = col * sub_w, row * sub_h  # Compute correct offset

        for point in centers:
            scaled_x = int(point["x"] + x_offset)
            scaled_y = int(point["y"] + y_offset)
            scaled_points.append({"x": scaled_x, "y": scaled_y})

    return scaled_points


@router.post("/model_combined_heatmap/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Splits an image, processes 3×3 sub-images, and merges the heatmap and cluster points."""
    image = Image.open(file.file)
    sub_images, sub_coords, full_size = split_image(image)

    heatmaps = []
    
    for sub_image in sub_images:
        count, elapsed_time, heatmap_tensor, cluster_centers, _, _, _, _ = demo.run_demo_image_nomongo(sub_image)
        to_pil = transforms.ToPILImage()
        # Convert tensor to PIL Image
        heatmap = to_pil(heatmap_tensor)

        heatmaps.append(heatmap)

    # Merge heatmaps and rescale cluster points
    final_heatmap = merge_heatmaps(heatmaps)

    # Convert final heatmap to response
    buffer = io.BytesIO()
    final_heatmap.save(buffer, format="PNG")
    buffer.seek(0)
    
    return Response(content=buffer.getvalue(), media_type="image/png")

@router.post("/model_combined_cluster/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Splits an image, processes 3×3 sub-images, and merges the heatmap and cluster points."""
    image = Image.open(file.file)
    sub_images, sub_coords, full_size = split_image(image)

    cluster_points = []
    
    for sub_image in sub_images:
        count, elapsed_time, heatmap_tensor, cluster_centers, _, _, _, _ = demo.run_demo_image_nomongo(sub_image)
        cluster_points.append(cluster_centers)

    # Merge heatmaps and rescale cluster points
    final_cluster_points = scale_cluster_points(cluster_points)
    

    return final_cluster_points

@router.post("/model_combined_count/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Splits an image, processes 3×3 sub-images, and merges the heatmap and cluster points."""
    image = Image.open(file.file)
    sub_images, sub_coords, full_size = split_image(image)

    Count=0
    
    for sub_image in sub_images:
        count, elapsed_time, heatmap_tensor, cluster_centers, _, _, pred_cnt_flt, _ = demo.run_demo_image_nomongo(sub_image)
        Count+=pred_cnt_flt

    return Count


@router.post("/model_combined_gridmap/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Splits an image, processes 3×3 sub-images, and merges the heatmap and cluster points."""
    image = Image.open(file.file)
    sub_images, sub_coords, full_size = split_image(image)

    Gridmap=[]
    
    for sub_image in sub_images:
        count, elapsed_time, heatmap_tensor, cluster_centers, _, _, pred_cnt_flt, _ = demo.run_demo_image_nomongo(sub_image)
        decimal_part, integer_part = math.modf(pred_cnt_flt)
        Gridmap.append([integer_part,decimal_part])

    return Gridmap



import io
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Depends, Response
from PIL import Image
import torch
import torchvision.transforms as transforms

# Your existing functions: get_current_user, helper_get_heatmap, split_image, demo.run_demo_image_nomongo

def combine_heatmaps(single_heatmap, grid_heatmap, weight_single=0.4, weight_grid=0.6, threshold=None):
    """
    Combines two heatmaps of different sizes using probability weighting.
    
    Parameters:
    - single_heatmap: PIL.Image, heatmap from full image (H, W)
    - grid_heatmap: PIL.Image, heatmap from split images (H', W')
    - weight_single: float, weight for single-image heatmap (default 0.4)
    - weight_grid: float, weight for grid heatmap (default 0.6)
    - threshold: float or None, optional threshold to remove low-confidence regions (0 to 1)
    
    Returns:
    - final_heatmap: PIL.Image, combined heatmap of size (H, W)
    """
    # Convert PIL images to NumPy arrays
    single_array = np.array(single_heatmap).astype(np.float32)
    grid_array = np.array(grid_heatmap).astype(np.float32)

    # Normalize both heatmaps to [0, 1]
    single_array = (single_array - single_array.min()) / (single_array.max() - single_array.min())
    grid_array = (grid_array - grid_array.min()) / (grid_array.max() - grid_array.min())

    # Resize grid heatmap to match single-image heatmap size
    target_size = (single_array.shape[1], single_array.shape[0])  # (Width, Height)
    grid_resized = cv2.resize(grid_array, target_size, interpolation=cv2.INTER_LINEAR)

    # Weighted combination
    final_array = (weight_single * single_array) + (weight_grid * grid_resized)

    # Normalize again after blending
    final_array = (final_array - final_array.min()) / (final_array.max() - final_array.min())

    # Apply thresholding if provided
    if threshold is not None:
        final_array[final_array < threshold] = 0

    # Convert back to PIL Image
    final_heatmap = Image.fromarray((final_array * 255).astype(np.uint8))

    return final_heatmap


@router.post("/model_final_heatmap/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Processes both full image and 3×3 sub-images, and combines their heatmaps probabilistically."""
    
    image = Image.open(file.file)
    # 1. Get heatmap from the full image
    single_heatmap_tensor = helper_get_heatmap(file)
    to_pil = transforms.ToPILImage()
    single_heatmap = to_pil(single_heatmap_tensor)  # Convert tensor to PIL image
    
    # 2. Get heatmap from the split images
    sub_images, sub_coords, full_size = split_image(image)
    heatmaps = []

    for sub_image in sub_images:
        _, _, heatmap_tensor, _, _, _, _, _ = demo.run_demo_image_nomongo(sub_image)
        heatmap = to_pil(heatmap_tensor)  # Convert tensor to PIL Image
        heatmaps.append(heatmap)

    # 3. Merge the split-image heatmaps
    merged_grid_heatmap = merge_heatmaps(heatmaps)

    # 4. Combine both heatmaps probabilistically
    final_heatmap = combine_heatmaps(single_heatmap, merged_grid_heatmap, weight_single=0.4, weight_grid=0.6, threshold=0.3)

    # 5. Convert final heatmap to response
    buffer = io.BytesIO()
    final_heatmap.save(buffer, format="PNG")
    buffer.seek(0)

    return Response(content=buffer.getvalue(), media_type="image/png")




def detect_local_maxima(density_map, threshold, min_distance=3):
    """
    Detects local maxima in the density map to identify individual bird locations.
    
    Args:
        density_map (torch.Tensor or np.ndarray): The density map of bird locations.
        threshold (float): The minimum density value to consider a point as a bird.
        min_distance (int): The minimum distance between two detected peaks.
    
    Returns:
        List[dict]: A list of dictionaries containing 'x' and 'y' coordinates of detected birds.
    """
    # Convert tensor to numpy array if needed
    if hasattr(density_map, 'cpu'):
        density_map = density_map.cpu().numpy()

    # Apply threshold
    mask = density_map > threshold

    # Find local maxima using a maximum filter
    local_max = (density_map == ndimage.maximum_filter(density_map, size=min_distance)) & mask
    y, x = np.where(local_max)  # Extract coordinates

    return [{'x': int(x[i]), 'y': int(y[i])} for i in range(len(x))]

def count_birds_from_heatmap(combined_heatmap, threshold=0.54, min_distance=3):
    """
    Counts the number of birds using local maxima detection from a combined heatmap.
    
    Args:
        combined_heatmap (PIL.Image): The final heatmap overlaid on the original image.
        threshold (float): The minimum intensity value to consider a point as a bird.
        min_distance (int): The minimum pixel distance between detected birds.
    
    Returns:
        int: Total bird count.
        List[dict]: List of detected bird coordinates.
    """
    # Convert heatmap to grayscale numpy array
    heatmap_array = np.array(combined_heatmap).astype(np.float32)

    if heatmap_array.ndim == 3:  # Convert RGB heatmap to grayscale if needed
        heatmap_array = np.mean(heatmap_array, axis=2)

    # Normalize to [0,1] range
    heatmap_array /= 255.0

    # Detect local maxima (bird locations)
    detected_birds = detect_local_maxima(heatmap_array, threshold, min_distance)

    return len(detected_birds), detected_birds



@router.post("/model_final_count/")
async def predict(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    """Processes both full image and 3×3 sub-images, and combines their heatmaps probabilistically."""
    
    image = Image.open(file.file)
    # 1. Get heatmap from the full image
    single_heatmap_tensor = helper_get_heatmap(file)
    to_pil = transforms.ToPILImage()
    single_heatmap = to_pil(single_heatmap_tensor)  # Convert tensor to PIL image
    
    # 2. Get heatmap from the split images
    sub_images, sub_coords, full_size = split_image(image)
    heatmaps = []

    for sub_image in sub_images:
        _, _, heatmap_tensor, _, _, _, _, _ = demo.run_demo_image_nomongo(sub_image)
        heatmap = to_pil(heatmap_tensor)  # Convert tensor to PIL Image
        heatmaps.append(heatmap)

    # 3. Merge the split-image heatmaps
    merged_grid_heatmap = merge_heatmaps(heatmaps)

    # 4. Combine both heatmaps probabilistically
    final_heatmap = combine_heatmaps(single_heatmap, merged_grid_heatmap, weight_single=0.4, weight_grid=0.6, threshold=0.3)

    pred_count, grid_counts = count_birds_from_heatmap(final_heatmap)

    return pred_count



    
