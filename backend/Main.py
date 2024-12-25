from fastapi import FastAPI, File, UploadFile,Response
from fastapi.responses import JSONResponse
from PIL import Image
from fastapi.middleware.cors import CORSMiddleware
import model_files.demomodified as demo
import torchvision.transforms.functional as TF
from torchvision import transforms
import io


app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def helper_get_heatmap(file: UploadFile = File(...)):
    image = Image.open(file.file)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return heatmap_file


@app.post("/model_heatmap/")
async def predict(file: UploadFile = File(...)):
    heatmap_file=helper_get_heatmap(file)
    to_pil = transforms.ToPILImage()
    image = to_pil(heatmap_file)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type="image/png")


def helper_get_gridmap(file: UploadFile = File(...)):
    image = Image.open(file.file)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return subgridcounts_error

@app.post("/model_gridmap/")
async def predict(file: UploadFile = File(...)):
    gridmap=helper_get_gridmap(file)
    return gridmap

def helper_get_count(file: UploadFile = File(...)):
    image = Image.open(file.file)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return pred_cnt_flt

@app.post("/model_count/")
async def predict(file: UploadFile = File(...)):
    count=helper_get_count(file)
    return count

def scale_coordinates(cluster_centers, original_size, target_size):
    tensor_width, tensor_height = original_size
    target_width, target_height = target_size

    scale_x = target_width / tensor_width
    scale_y = target_height / tensor_height

    # Flatten the list of lists and scale each point
    scaled_points = [
        {"x": int(point["x"] * scale_x), "y": int(point["y"] * scale_y)}
        for point in cluster_centers
    ]
    return scaled_points

def helper_get_cluster1(file: UploadFile = File(...)):
    image = Image.open(file.file)
    original_tensor_size = (480, 384)  # Tensor size (width, height)
    target_image_size = image.size  # Actual image size (width, height)
    print(image.size)

    # Replace the demo logic with the real function generating cluster centers
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions, subgrid_counts, pred_cnt_flt, subgridcounts_error = demo.run_demo_image_nomongo(image)
    print(len(cluster_centers[0]))
    # Scale the cluster centers
    scaled_cluster_centers = scale_coordinates(cluster_centers[0], original_tensor_size, target_image_size)
    print(len(scaled_cluster_centers))
    return scaled_cluster_centers

def helper_get_cluster2(file: UploadFile = File(...)):
    image = Image.open(file.file)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return cluster_centers

@app.post("/model_cluster/")
async def predict(file: UploadFile = File(...)):
    cluster_centers=helper_get_cluster1(file)
    return cluster_centers

