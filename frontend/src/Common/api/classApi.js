import axiosInstance from "../../ObjectDetection/api/api";

export const fetchClasses = () => axiosInstance.get("/classes/");

export const updateClass = (id, name) =>
  axiosInstance.put(`/classes/${id}`, { id, name });

export const bulkUpdateClasses = (names) =>
  axiosInstance.post("/classes/bulk", names);