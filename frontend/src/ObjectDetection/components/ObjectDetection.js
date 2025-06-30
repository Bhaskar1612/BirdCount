import React, { useEffect, useState, useCallback } from "react";
import ClassFilter from "./ClassFilter";
import Collage from "./Collage";
import Modal from "./Modal";
import styles from "./styles.module.css";
import {
  getImages,
  getImageUrl,
  downloadAnnotatedImages,
} from "../api/imageApi";
import { logError } from "../utils/error.js";

function ObjectDetection({ uploadedImageIds }) {
  const [images, setImages] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [columnImages, setColumnImages] = useState([[], [], [], [], []]);
  const [selectedClass, setSelectedClass] = useState("All");
  const [classList, setClassList] = useState([]);
  const [isDownloading, setIsDownloading] = useState(false);
  const [boxCountFilter, setBoxCountFilter] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);

  const loadImages = useCallback(async () => {
    try {
      const data = await getImages(
        selectedClass,
        boxCountFilter,
        searchQuery,
        currentPage,
        pageSize
      );

      const imageList = (data.images || []).map((img) =>
        typeof img === "object" ? img : { id: img }
      );
      const unique = imageList.filter(
        (img, i, self) => i === self.findIndex((t) => t.id === img.id)
      );
      const uploadedSet = new Set(uploadedImageIds);
      const sortedImages = unique.sort((a, b) => {
        const aUploaded = uploadedSet.has(a.id);
        const bUploaded = uploadedSet.has(b.id);

        if (aUploaded && bUploaded) {
          return (
            uploadedImageIds.indexOf(b.id) - uploadedImageIds.indexOf(a.id)
          );
        }
        if (aUploaded) return -1;
        if (bUploaded) return 1;
        return 0;
      });
      const withSrc = sortedImages.map((img) => ({
        ...img,
        src: getImageUrl(img.id),
      }));

      setImages(withSrc);
      setTotal(data.total);
      distributeImages(withSrc);
    } catch (error) {
      logError("Error fetching images:", error);
    }
  }, [selectedClass, boxCountFilter, searchQuery, currentPage, pageSize]);

  useEffect(() => {
    loadImages();
  }, [uploadedImageIds, loadImages]);

  const distributeImages = useCallback((imageList) => {
    const columns = Array.from({ length: 5 }, () => []);
    imageList.forEach((imageData, index) => {
      const columnIndex = index % 5;
      columns[columnIndex].push(imageData);
    });

    setColumnImages(columns);
  }, []);

  const handleDownloadAll = useCallback(async () => {
    if (!images.length || isDownloading) {
      return;
    }
    setIsDownloading(true);
    try {
      const blob = await downloadAnnotatedImages();
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "annotated-images.zip");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      logError("Error downloading images:", error);
      alert("Failed to download images");
    } finally {
      setIsDownloading(false);
    }
  }, [images, isDownloading]);

  const handleBoxCountFilterChange = useCallback((filterString) => {
    setBoxCountFilter(filterString);
  }, []);

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className={styles["App"]}>
      <main>
        <div className={styles["object-detection-controls"]}>
          <ClassFilter
            onSearch={setSearchQuery}
            onClassSelect={setSelectedClass}
            selectedClass={selectedClass}
            setClassList={setClassList}
            onBoxCountFilterChange={handleBoxCountFilterChange}
            selectedBoxCountFilter={boxCountFilter}
          />
          <button
            className={styles["download-button"]}
            onClick={handleDownloadAll}
            disabled={!images.length || isDownloading}
            title={
              !images.length ? "No images to download" : "Download All Images"
            }
          >
            {isDownloading ? "Downloading..." : "Download All Images"}
          </button>
        </div>
        {images.length === 0 ? (
          <img
            src="https://placehold.co/600x400?text=No+Images+Available&color=cccccc&text-color=666666&font=roboto"
            alt="No images available"
            className={styles["fallback-image"]}
          />
        ) : (
          <Collage
            columnImages={columnImages}
            handleImageClick={setSelectedImage}
          />
        )}
        {selectedImage && (
          <Modal
            selectedImage={selectedImage}
            handleCloseModal={() => setSelectedImage(null)}
            classList={classList}
            isForActiveLearning={false}
          />
        )}
        {images.length > 0 && (
          <div className={styles["pagination"]}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              disabled={currentPage === 1}
            >
              Prev
            </button>
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() =>
                setCurrentPage((p) => (p < totalPages ? p + 1 : totalPages))
              }
              disabled={currentPage === totalPages}
            >
              Next
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default ObjectDetection;
