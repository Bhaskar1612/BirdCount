import React, { useState } from "react";
import { uploadImages, uploadZipFolder } from "../api/uploadApi";
import { logError } from "../utils/error.js";
import styles from "./styles.module.css";

const UploadSection = ({ onUploadSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [showConsentDialog, setShowConsentDialog] = useState(false);
  const [pendingUpload, setPendingUpload] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const uploadConfigs = {
    file: {
      accept: "image/*",
      icon: "🗒️",
      title: "Upload Image File",
      description: "Click or drag image files here",
      handler: uploadImages,
      processResult: (result) => (Array.isArray(result) ? result : [result]),
    },
    folder: {
      accept: ".zip,.rar,.tar,.gz,.bz2,.7z",
      icon: "🗂️",
      title: "Upload Zip Folder",
      description: "Click or drag zip folders here",
      handler: uploadZipFolder,
      processResult: (result) => (Array.isArray(result) ? result : []),
    },
  };

  const handleUpload = (event, config) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    setPendingUpload({ files, config });
    setShowConsentDialog(true);
  };

  const handleConsent = async (hasConsent) => {
    setShowConsentDialog(false);
    if (!pendingUpload) return;

    try {
      setIsLoading(true);
      setError(null);
      setUploadStatus(null);
      setUploadProgress(0);

      const { files, config } = pendingUpload;
      const result = await config.handler(
        files,
        hasConsent,
        (uploadProgressValue) => {
          setUploadProgress(uploadProgressValue);
        },
        (downloadProgressValue) => {
          console.log("Download progress:", downloadProgressValue);
        }
      );

      const processedIds = config.processResult(result);
      if (processedIds.length > 0) {
        onUploadSuccess(processedIds);
        setUploadStatus("upload-success");
      } else {
        throw new Error("No images were processed successfully");
      }
    } catch (error) {
      logError("Upload error:", error);
      setError(error.message);
      setUploadStatus("upload-error");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles["upload-section"]}>
      {showConsentDialog && (
        <div className={styles["consent-dialog"]}>
          <div className={styles["consent-content"]}>
            <h3>Data Usage Consent</h3>
            <p>Please note:</p>
            <ul>
              <li>
                Without consent, images will be deleted when you close the
                website
              </li>
              <li>With consent, images will be saved for model training</li>
              <li>You can still use all features without consent</li>
              <li>Download annotations if you want to keep them</li>
            </ul>
            <div className={styles["consent-buttons"]}>
              <button onClick={() => handleConsent(false)}>
                Don't Save Images
              </button>
              <button onClick={() => handleConsent(true)}>
                Allow Model Training
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={styles["upload-buttons"]}>
        {Object.entries(uploadConfigs).map(([key, config]) => (
          <div
            key={key}
            className={`${styles["upload-button"]} ${
              isLoading ? styles["loading"] : ""
            }`}
          >
            <input
              type="file"
              accept={config.accept}
              onChange={(e) => handleUpload(e, config)}
              multiple={true}
              disabled={isLoading}
            />
            <div className={styles["upload-content"]}>
              <span className={styles["upload-icon"]}>{config.icon}</span>
              <h3>{config.title}</h3>
              {isLoading && key === "folder" ? (
                <div>
                  <p>Uploading... {uploadProgress}%</p>
                  <progress value={uploadProgress} max="100" />
                </div>
              ) : (
                <p>{isLoading ? "Uploading..." : config.description}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {(uploadStatus || error) && (
        <div
          className={`${styles["status-message"]} ${
            uploadStatus === "upload-success"
              ? styles["success"]
              : styles["error"]
          }`}
        >
          {error ||
            (uploadStatus === "upload-success"
              ? "Upload successful!"
              : "Upload failed!")}
        </div>
      )}
    </div>
  );
};

export default UploadSection;
