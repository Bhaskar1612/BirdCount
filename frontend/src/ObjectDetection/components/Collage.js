import React, { useState, useEffect } from "react";
import styles from "./styles.module.css";

const Collage = ({
  columnImages = [],
  handleImageClick,
  activeLearning = false,
  onSelectionChange,
}) => {
  const [imageUrls, setImageUrls] = useState({});
  const [selectedImageIds, setSelectedImageIds] = useState([]);

  useEffect(() => {
    const loadImageUrls = async () => {
      const urls = {};
      for (
        let columnIndex = 0;
        columnIndex < columnImages.length;
        columnIndex++
      ) {
        const images = columnImages[columnIndex];
        for (let imageIndex = 0; imageIndex < images.length; imageIndex++) {
          const image = images[imageIndex];
          if (!image || typeof image !== "object") continue;
          const { src, id } = image;
          urls[id] = src;
        }
      }
      setImageUrls(urls);
    };

    loadImageUrls();
  }, [columnImages]);

  useEffect(() => {
    if (onSelectionChange) onSelectionChange(selectedImageIds);
  }, [selectedImageIds, onSelectionChange]);

  const handleSelectImage = (id, e) => {
    e.stopPropagation();
    setSelectedImageIds((prev) => {
      return prev.includes(id)
        ? prev.filter((item) => item !== id)
        : [...prev, id];
    });
  };

  return (
    <div className={styles["collage"]}>
      {columnImages.map((images, columnIndex) => {
        if (!Array.isArray(images)) return null;
        return (
          <div key={columnIndex} className={styles["collage-column"]}>
            {images.map((image) => {
              if (!image || typeof image !== "object") return null;
              const { filename, id, src } = image;
              if (!src || !filename) return null;

              const isSelected = selectedImageIds.includes(id);
              return (
                <div
                  key={id}
                  className={`${styles["collage-image-wrapper"]} ${
                    isSelected ? styles["selected-image"] : ""
                  }`}
                  onClick={() => handleImageClick(id)}
                >
                  {activeLearning && (
                    <input
                      type="checkbox"
                      className={styles["image-select-checkbox"]}
                      checked={isSelected}
                      onChange={(e) => handleSelectImage(id, e)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
                  <img
                    src={src}
                    alt={filename}
                    className={styles["collage-image"]}
                    draggable={false}
                  />
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export default Collage;
