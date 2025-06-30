import axiosInstance from "./api.js";
import { handleImageApiError, handleRawImageError } from "../utils/error.js";

export const getClasses = async () => {
  try {
    const response = await axiosInstance.get("/classes/"); // note trailing slash
    return response.data;
  } catch (error) {
    handleImageApiError(error);
    return []; // safe default
  }
};

export const getImageUrl = (imageId) =>
  `${process.env.REACT_APP_API_BASE_URL}/images?task=object-detection&image_id=${imageId}`;

export async function getImages(
  selectedClass,
  boxCountFilter,
  query,
  page = 1,
  pageSize = 50 
) {
  try {
    const response = await axiosInstance.get("/images", {
      params: {
        task: "object-detection", 
        class_id: selectedClass !== "All" ? selectedClass : undefined,
        box_count_filter: boxCountFilter,
        query,
        page,
        page_size: pageSize,
      },
    });
    return response.data; // { images, page, page_size, total }
  } catch (error) {
    handleImageApiError(error);
    return { images: [], page, page_size: pageSize, total: 0 };
  }
}

export const getImageBoxes = async (imageId, boxType = "user") => {
  try {
    const response = await axiosInstance.get("/bounding-boxes", {
      params: { image_id: imageId, box_type: boxType },
    });
    const boxes = response.data.boxes.map((boxArray) => ({
      id: boxArray[0],
      image_id: boxArray[1],
      class_id: boxArray[2],
      x: boxArray[3],
      y: boxArray[4],
      width: boxArray[5],
      height: boxArray[6],
      confidence: boxArray[7],
      created_at: boxArray[8],
    }));
    return { boxes };
  } catch (error) {
    handleImageApiError(error);
    return { boxes: [] }; // safe default
  }
};

export const saveImageBoxes = async (imageId, boxes, boxType = "user") => {
  try {
    const response = await axiosInstance.post(
      `/bounding-boxes?image_id=${imageId}&box_type=${boxType}`,
      boxes
    );
    return response;
  } catch (error) {
    handleImageApiError(error);
    throw new Error(
      error.response?.data?.detail || "Network error while posting annotations"
    );
  }
};

export const cleanupNonConsented = async () => {
  try {
    // no trailing slash avoids 307 redirect
    const response = await axiosInstance.delete("/cleanup");
    return response.data;
  } catch (error) {
    handleImageApiError(error);
  }
};

export const downloadAnnotatedImages = async () => {
  try {
    const response = await axiosInstance.get(
      "/download?task=object-detection",
      {
        responseType: "blob",
      }
    );
    return response.data;
  } catch (error) {
    handleImageApiError(error);
    throw new Error("Network error while downloading images");
  }
};

export const getActiveLearningImages = async (limit = 5) => {
  try {
    const response = await axiosInstance.get(
      `/images?task=object-detection&page=active-learning&limit=${limit}`
    );
    return response.data;
  } catch (error) {
    handleImageApiError(error);
    return [];
  }
};
