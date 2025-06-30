import axiosInstance from "./api.js";
import { handleUploadApiError } from "../utils/error.js";

const allowedExtensions = ["jpeg", "jpg", "png"];

export const uploadImages = async (files, consent = false) => {
  const validFiles = files.filter((file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    return allowedExtensions.includes(ext);
  });
  if (validFiles.length === 0) {
    throw new Error(
      `No supported image files selected. Allowed types: ${allowedExtensions.join(
        ", "
      )}`
    );
  }

  const uploadedIds = [];
  for (const file of validFiles) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("consent", consent);
    formData.append("type", "image");
    formData.append("task", "object-detection");

    try {
      const response = await axiosInstance.post("/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      const ids = response.data?.uploaded_image_ids || [];
      if (!Array.isArray(ids)) {
        throw new Error("Server response uploaded_image_ids is not an array");
      }
      uploadedIds.push(...ids);
    } catch (error) {
      handleUploadApiError(error);
    }
  }
  return uploadedIds;
};

export const uploadZipFolder = async (
  files,
  consent = false,
  onUploadProgress
) => {
  const formData = new FormData();
  for (const file of files) {
    formData.append("file", file);
  }
  formData.append("consent", consent);
  formData.append("type", "folder");
  formData.append("task", "object-detection");

  return new Promise((resolve, reject) => {
    fetch(`${process.env.REACT_APP_API_BASE_URL}/upload`, {
      method: "POST",
      body: formData,
      credentials: "include",
    })
      .then((response) => {
        const reader = response.body.getReader();
        const textDecoder = new TextDecoder();

        function read() {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                resolve();
                return;
              }

              const chunk = textDecoder.decode(value);
              const events = chunk.split("\n\n");

              events.forEach((event) => {
                if (event.trim() !== "") {
                  try {
                    const data = JSON.parse(event.replace("data: ", ""));
                    if (data.progress !== undefined) {
                      onUploadProgress(data.progress);
                    } else if (data.message) {
                      console.log("Upload completed:", data.message);
                      resolve(data.uploaded_image_ids);
                    }
                  } catch (e) {
                    console.error("Error parsing SSE data:", e, event);
                    reject(e);
                  }
                }
              });

              read();
            })
            .catch((error) => {
              console.error("Error reading stream:", error);
              reject(error);
            });
        }

        read();
      })
      .catch((error) => {
        console.error("Upload failed:", error);
        reject(error);
      });
  });
};
