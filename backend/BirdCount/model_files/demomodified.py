import time
import numpy as np
from io import BytesIO
import torch
import torch.nn as nn
from torchvision import transforms
import torchvision.transforms.functional as TF
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import timm
from sklearn.cluster import DBSCAN
import numpy as np
from BirdCount.model_files.misc import make_grid
from BirdCount.model_files import models_mae_cross
import matplotlib.cm as cm
device = torch.device('cuda')
import warnings  
global model, model_without_ddp
warnings.filterwarnings('ignore')

"""
python demo.py
"""


class measure_time(object):
    def __enter__(self):
        self.start = time.perf_counter_ns()
        return self

    def __exit__(self, typ, value, traceback):
        self.duration = (time.perf_counter_ns() - self.start) / 1e9


def plot_heatmap(density_map, count, buffer):
    # Make sure that this function now writes to a BytesIO buffer instead of saving to a file path
    fig, ax = plt.subplots()
    im = ax.imshow(density_map.cpu().numpy(), cmap='viridis')
    # ax.text(0, 0, f'Count: {count:.2f}', color='white', fontsize=12, va='top', ha='left', backgroundcolor='black')
    # plt.colorbar(im)
    fig.canvas.draw()  # This line draws the figure on the canvas so that it can be saved
    plt.savefig(buffer, format='png')
    plt.close()



def load_image_nomongo(image):
    W, H = image.size

    # Resize the image size so that the height is 384
    new_H = 384
    new_W = 480
    scale_factor_H = float(new_H) / H
    scale_factor_W = float(new_W) / W
    print(f"Original image size: {W}x{H}")
    print(f"Processed image size: {new_W}x{new_H}")
    print(f"Scaling factors: {scale_factor_W}, {scale_factor_H}")
    image = transforms.Resize((new_H, new_W))(image)
    Normalize = transforms.Compose([transforms.ToTensor()])
    image = Normalize(image)

    # Coordinates of the exemplar bound boxes
    bboxes = [
        [[136, 98], [173, 127]],
        [[209, 125], [742, 150]],
        [[602, 168], [758, 200]]
]
    boxes = list()
    rects = list()
    for bbox in bboxes:
        x1 = int(bbox[0][0] * scale_factor_W)
        y1 = int(bbox[0][1] * scale_factor_H)
        x2 = int(bbox[1][0] * scale_factor_W)
        y2 = int(bbox[1][1] * scale_factor_H)
        rects.append([y1, x1, y2, x2])
        bboxnew = image[:, y1:y2 + 1, x1:x2 + 1]
        bboxnew = transforms.Resize((64, 64))(bboxnew)
        boxes.append(bboxnew.numpy())

    boxes = np.array(boxes)
    boxes = torch.Tensor(boxes)

    return image, boxes, rects



def run_one_image_nomongo(samples, boxes, pos, model, orig_image_size):
    _, _, h, w = samples.shape
    orig_h, orig_w = orig_image_size

    # Calculate the scaling factors
    print("test : ",orig_h, orig_w, h, w)
    scale_factor_H = orig_h / h
    scale_factor_W = orig_w / w
    s_cnt = 0
    for rect in pos:
        if rect[2] - rect[0] < 10 and rect[3] - rect[1] < 10:
            s_cnt += 1
    if s_cnt >= 1:
        r_densities = []
        r_images = []
        r_images.append(TF.crop(samples[0], 0, 0, int(h / 3), int(w / 3)))  # 1
        r_images.append(TF.crop(samples[0], 0, int(w / 3), int(h / 3), int(w / 3)))  # 3
        r_images.append(TF.crop(samples[0], 0, int(w * 2 / 3), int(h / 3), int(w / 3)))  # 7
        r_images.append(TF.crop(samples[0], int(h / 3), 0, int(h / 3), int(w / 3)))  # 2
        r_images.append(TF.crop(samples[0], int(h / 3), int(w / 3), int(h / 3), int(w / 3)))  # 4
        r_images.append(TF.crop(samples[0], int(h / 3), int(w * 2 / 3), int(h / 3), int(w / 3)))  # 8
        r_images.append(TF.crop(samples[0], int(h * 2 / 3), 0, int(h / 3), int(w / 3)))  # 5
        r_images.append(TF.crop(samples[0], int(h * 2 / 3), int(w / 3), int(h / 3), int(w / 3)))  # 6
        r_images.append(TF.crop(samples[0], int(h * 2 / 3), int(w * 2 / 3), int(h / 3), int(w / 3)))  # 9

        pred_cnt = 0
        with measure_time() as et:
            for r_image in r_images:
                r_image = transforms.Resize((h, w))(r_image).unsqueeze(0)
                density_map = torch.zeros([h, w])
                density_map = density_map.to(device, non_blocking=True)
                start = 0
                prev = -1
                with torch.no_grad():
                    while start + 383 < w:
                        output, = model(r_image[:, :, :, start:start + 384], boxes, 3)
                        output = output.squeeze(0)
                        b1 = nn.ZeroPad2d(padding=(start, w - prev - 1, 0, 0))
                        d1 = b1(output[:, 0:prev - start + 1])
                        b2 = nn.ZeroPad2d(padding=(prev + 1, w - start - 384, 0, 0))
                        d2 = b2(output[:, prev - start + 1:384])

                        b3 = nn.ZeroPad2d(padding=(0, w - start, 0, 0))
                        density_map_l = b3(density_map[:, 0:start])
                        density_map_m = b1(density_map[:, start:prev + 1])
                        b4 = nn.ZeroPad2d(padding=(prev + 1, 0, 0, 0))
                        density_map_r = b4(density_map[:, prev + 1:w])

                        density_map = density_map_l + density_map_r + density_map_m / 2 + d1 / 2 + d2

                        prev = start + 383
                        start = start + 128
                        if start + 383 >= w:
                            if start == w - 384 + 128:
                                break
                            else:
                                start = w - 384

                pred_cnt += torch.sum(density_map / 60).item()
                r_densities += [density_map]
    else:
        density_map = torch.zeros([h, w])
        density_map = density_map.to(device, non_blocking=True)
        start = 0
        prev = -1
        with measure_time() as et:
            with torch.no_grad():
                while start + 383 < w:
                    output, = model(samples[:, :, :, start:start + 384], boxes, 3)
                    output = output.squeeze(0)
                    b1 = nn.ZeroPad2d(padding=(start, w - prev - 1, 0, 0))
                    d1 = b1(output[:, 0:prev - start + 1])
                    b2 = nn.ZeroPad2d(padding=(prev + 1, w - start - 384, 0, 0))
                    d2 = b2(output[:, prev - start + 1:384])

                    b3 = nn.ZeroPad2d(padding=(0, w - start, 0, 0))
                    density_map_l = b3(density_map[:, 0:start])
                    density_map_m = b1(density_map[:, start:prev + 1])
                    b4 = nn.ZeroPad2d(padding=(prev + 1, 0, 0, 0))
                    density_map_r = b4(density_map[:, prev + 1:w])

                    density_map = density_map_l + density_map_r + density_map_m / 2 + d1 / 2 + d2

                    prev = start + 383
                    start = start + 128
                    if start + 383 >= w:
                        if start == w - 384 + 128:
                            break
                        else:
                            start = w - 384

            pred_cnt = torch.sum(density_map / 60).item()

    # Normalize density_map for visualization
    density_map = density_map.to('cuda')
    samples = samples.to('cuda')

    # Normalize density_map for visualization
    density_normalized = density_map / density_map.max()

    # Convert density map to RGBA image using a colormap
    colormap = cm.get_cmap('jet')  # You can choose any available colormap
    density_colormap = colormap(density_normalized.cpu().detach().numpy())  # Move to CPU and convert to numpy

    # Convert RGBA image to RGB by ignoring the alpha channel
    density_rgb = density_colormap[...,:3]

    # Convert to tensor and move to GPU
    density_rgb_tensor = torch.from_numpy(density_rgb).float().permute(2, 0, 1).to('cuda')

    # Resize density_rgb_tensor to match the size of the original image
    density_resized = TF.resize(density_rgb_tensor, samples.shape[2:])

    # Blend the original image with the density map
    # Adjust alpha to change the transparency of the overlay
    alpha = 0.5
    blended_image = (1 - alpha) * samples[0] + alpha * density_resized
    
    # Clamp the values to be between 0 and 1
    blended_image_clamped = torch.clamp(blended_image, 0, 1)
    
    # Save or display the blended image
    # Convert blended_image_clamped to PIL image to save or display
    blended_image_pil = TF.to_pil_image(blended_image_clamped.cpu())
    blended_image_buffer = BytesIO()
    blended_image_pil.save(blended_image_buffer, format='PNG')
    blended_image_buffer.seek(0)
    #blended_image_file_id = fs.put(blended_image_buffer, filename='blended_heatmap.png', content_type='image/png')
    e_cnt = 0
    for rect in pos:
        e_cnt += torch.sum(density_map[rect[0]:rect[2] + 1, rect[1]:rect[3] + 1] / 60).item()
    e_cnt = e_cnt / 3
    if e_cnt > 1.8:
        pred_cnt /= e_cnt

    # Visualize the prediction
    fig = samples[0]
    box_map = torch.zeros([fig.shape[1], fig.shape[2]])
    box_map = box_map.to(device, non_blocking=True)
    for rect in pos:
        for i in range(rect[2] - rect[0]):
            box_map[min(rect[0] + i, fig.shape[1] - 1), min(rect[1], fig.shape[2] - 1)] = 10
            box_map[min(rect[0] + i, fig.shape[1] - 1), min(rect[3], fig.shape[2] - 1)] = 10
        for i in range(rect[3] - rect[1]):
            box_map[min(rect[0], fig.shape[1] - 1), min(rect[1] + i, fig.shape[2] - 1)] = 10
            box_map[min(rect[2], fig.shape[1] - 1), min(rect[1] + i, fig.shape[2] - 1)] = 10
    box_map = box_map.unsqueeze(0).repeat(3, 1, 1)
    pred = density_map.unsqueeze(0).repeat(3, 1, 1) if s_cnt < 1 \
        else make_grid(r_densities, h, w).unsqueeze(0).repeat(3, 1, 1)
    fig = fig + box_map + pred / 2
    fig = torch.clamp(fig, 0, 1)
    heatmap_buffer = BytesIO()
    plot_heatmap(density_map, pred_cnt, heatmap_buffer)
    heatmap_buffer.seek(0)
    #heatmap_file_id = fs.put(heatmap_buffer, filename='heatmap.png', content_type='image/png')
    pred_cnt_ceil = int(pred_cnt + 0.99)
    # Thresholding the density map
   
    # Convert cluster centers to a format suitable for JSON serialization
    # This will be useful for sending data to the frontend
    
     # Include cluster_centers_json in the return statement
    return pred_cnt_ceil, et.duration, blended_image_clamped, density_map, pred_cnt
  




import numpy as np
import scipy.ndimage as ndimage

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

# Example usage:
# detected_birds = detect_local_maxima(density_map, threshold=0.5, min_distance=3)
# print(detected_birds)


# Prepare model
model = models_mae_cross.__dict__['mae_vit_base_patch16'](norm_pix_loss='store_true')
model.to(device)
model_without_ddp = model

from pathlib import Path

checkpoint_path = Path(__file__).resolve().parent / 'pth/original.pth'
checkpoint = torch.load(checkpoint_path, map_location='cuda')
model_without_ddp.load_state_dict(checkpoint['model'], strict=False)
# print("Resume checkpoint %s" % './checkpoint-400.pth')

model.eval()

def run_demo_image_nomongo(image):
    basewidth = 1000
    wpercent = (basewidth / float(image.size[0]))
    hsize = int((float(image.size[1]) * float(wpercent)))
    image = image.resize((basewidth, hsize))
    samples, boxes, pos = load_image_nomongo(image)
    samples = samples.unsqueeze(0).to(device, non_blocking=True)
    boxes = boxes.unsqueeze(0).to(device, non_blocking=True)
    orig_image_size = samples.shape[2:]  # Capture the original image size
    # Now, run_one_image returns the density_map as well
    pred_cnt_int, elapsed_time, heatmap_file, density_map, pred_cnt_flt = run_one_image_nomongo(samples, boxes, pos, model, orig_image_size)

    # Compute scale factors based on the original image size and the processed size
    scale_factors = {'W': orig_image_size[1]/density_map.shape[1], 'H': orig_image_size[0]/density_map.shape[0]}
    print(scale_factors)

    # Generate multiple sets of cluster centers

    cluster_centers_sets = detect_local_maxima(density_map, threshold=0.25, min_distance=3)

    density_map_height = density_map.shape[0]
    density_map_width = density_map.shape[1]
    subgrid_counts = []
    #create a 3x3 grid in density_map, then sum up each grid and append to subgrid_counts, use size of map instead of hardcoding
    for i in range(3):
        for j in range(3):
            
            subgrid = density_map[int(i * density_map_height / 3):int((i + 1) * density_map_height / 3), int(j * density_map_width / 3):int((j + 1) * density_map_width / 3)]
            subgrid_count = torch.sum(subgrid / 60).item()
            subgrid_counts.append(subgrid_count)

    # subgridcnts are floats, put into format of [(int, float), (int, float), ...] where int is rounded (not floored) and flt is decimal part
    subgrid_counts_with_error = []
    for subgrid_count in subgrid_counts:
        subgrid_count_int = int(subgrid_count)
        subgrid_count_flt = subgrid_count - subgrid_count_int
        subgrid_counts_with_error.append((subgrid_count_int, subgrid_count_flt))
    pred_cnt_flt =  sum(subgrid_counts)
    pred_cnt_int = int(pred_cnt_flt + 0.99)
    


    return pred_cnt_int, elapsed_time, heatmap_file, cluster_centers_sets, orig_image_size, subgrid_counts, pred_cnt_flt, subgrid_counts_with_error

