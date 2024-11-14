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
    print(heatmap_file.shape)
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

def helper_get_cluster(file: UploadFile = File(...)):
    image = Image.open(file.file)
    count, elapsed_time, heatmap_file, cluster_centers, image_dimensions,subgrid_counts,pred_cnt_flt,subgridcounts_error = demo.run_demo_image_nomongo(image)
    return cluster_centers

@app.post("/model_cluster/")
async def predict(file: UploadFile = File(...)):
    cluster_centers=helper_get_cluster(file)
    return cluster_centers

