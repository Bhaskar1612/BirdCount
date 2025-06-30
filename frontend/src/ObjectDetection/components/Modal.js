import React, { useCallback, useEffect, useRef, useState } from "react";
import BoundingBox from "./BoundingBox";
import styles from "./styles.module.css";
import { getImageBoxes, saveImageBoxes, getImageUrl } from "../api/imageApi.js";
import { logError } from "../utils/error.js";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const Modal = ({
  selectedImage,
  handleCloseModal,
  classList,
  isForActiveLearning = false,
  annotateMode = false,
  onNextImage,
  onPrevImage,
}) => {
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [boxes, setBoxes] = useState([]);
  const [imageUrl, setImageUrl] = useState("");

  const imageRef = useRef(null);
  const modalRef = useRef(null);
  const modalBackgroundRef = useRef(null);
  const nextIdRef = useRef(1);
  const [isInteractingWithBoundingBox, setIsInteractingWithBoundingBox] =
    useState(false);
  const filteredClassList = classList.filter(
    (cls) =>
      cls.name.trim().toLowerCase() !== "all" &&
      cls.name.trim().toLowerCase() !== "blan_blan"
  );

  useEffect(() => {
    const fetchBoxes = async () => {
      try {
        const boxType = isForActiveLearning ? "active" : "user";
        const data = await getImageBoxes(selectedImage, boxType);
        const filteredBoxes = data.boxes.filter(
          (box) => box.width > 0 && box.height > 0
        );
        setBoxes(filteredBoxes);
        if (filteredBoxes.length > 0) {
          nextIdRef.current =
            Math.max(...filteredBoxes.map((box) => box.id)) + 1;
        }
      } catch (error) {
        logError("Error fetching boxes:", error);
        toast.error("Error fetching boxes.");
      }
    };

    fetchBoxes();
  }, [selectedImage, isForActiveLearning]);

  useEffect(() => {
    if (!selectedImage) return;
    const fetchImageUrl = async () => {
      try {
        const url = await getImageUrl(selectedImage);
        setImageUrl(url);
      } catch (error) {
        logError("Error fetching image URL:", error);
      }
    };
    fetchImageUrl();
  }, [selectedImage]);

  useEffect(() => {
    if (!selectedImage) return;
    const updateImageSize = () => {
      if (imageRef.current) {
        const { width, height } = imageRef.current.getBoundingClientRect();
        setImageSize({ width, height });
      }
    };
    if (imageUrl) {
      const loadingImage = new Image();
      loadingImage.src = imageUrl;
      loadingImage.onload = () => {
        setNaturalSize({
          width: loadingImage.naturalWidth,
          height: loadingImage.naturalHeight,
        });
        updateImageSize();
      };
    }
    window.addEventListener("resize", updateImageSize);
    return () => window.removeEventListener("resize", updateImageSize);
  }, [selectedImage, imageUrl]);

  const handleBoxChange = useCallback((newBoxData, id) => {
    setBoxes((prevBoxes) =>
      prevBoxes.map((box) =>
        box.id === id
          ? {
              ...box,
              ...newBoxData,
              category: newBoxData.category,
              class_id: newBoxData.category,
            }
          : box
      )
    );
  }, []);

  const defaultCategory = filteredClassList[0]?.id || null;

  const handleAddBox = useCallback(() => {
    if (filteredClassList.length === 0) return;
    setBoxes((prevBoxes) => [
      ...prevBoxes,
      {
        id: nextIdRef.current,
        detection_id: null,
        x: 100,
        y: 100,
        width: 200,
        height: 200,
        category: defaultCategory,
      },
    ]);
    nextIdRef.current += 1;
  }, [filteredClassList, defaultCategory]);

  const handleRemoveBox = useCallback((id) => {
    setBoxes((prevBoxes) => {
      return prevBoxes.filter((box) => box.id !== id);
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedImage) return;

    const blanBlanClass = classList.find(
      (cls) => cls.name.trim().toLowerCase() === "blan_blan"
    );
    const defaultClassId = filteredClassList[0]?.id || -1;

    let boxData;
    if (boxes.length === 0) {
      const placeholderClassId = blanBlanClass
        ? blanBlanClass.id
        : defaultClassId;
      if (!blanBlanClass) {
        console.warn(
          "blan_blan class not found, using default ID for placeholder."
        );
      }
      console.log(
        `Saving with no boxes, using class ID: ${placeholderClassId}`
      );
      boxData = [
        {
          class_id: placeholderClassId,
          x: 0,
          y: 0,
          width: 0,
          height: 0,
          confidence: 0.0,
        },
      ];
    } else {
      boxData = boxes.map((box) => {
        const classId =
          box.class_id !== undefined
            ? box.class_id
            : parseInt(box.category, 10);
        if (
          isNaN(classId) ||
          !filteredClassList.some(
            (cls) => String(cls.id) === String(classId)
          ) ||
          (blanBlanClass && String(classId) === String(blanBlanClass.id))
        ) {
          console.warn(
            `Invalid or disallowed class_id ${classId}, using default ${defaultClassId}`
          );
          return {
            class_id: defaultClassId,
            x: parseFloat(box.x),
            y: parseFloat(box.y),
            width: parseFloat(box.width),
            height: parseFloat(box.height),
            confidence: parseFloat(box.confidence || 1.0),
          };
        }
        return {
          class_id: classId,
          x: parseFloat(box.x),
          y: parseFloat(box.y),
          width: parseFloat(box.width),
          height: parseFloat(box.height),
          confidence: parseFloat(box.confidence || 1.0),
        };
      });
    }

    try {
      const boxType = isForActiveLearning ? "active" : "user";
      await saveImageBoxes(selectedImage, boxData, boxType);
      toast.success("Changes saved successfully!");
    } catch (error) {
      logError("Error saving annotations:", error);
      toast.error("Failed to save changes.");
    }
  }, [selectedImage, boxes, classList, filteredClassList, isForActiveLearning]);

  const handleClickOutside = (e) => {
    if (
      modalBackgroundRef.current &&
      modalBackgroundRef.current === e.target &&
      !isInteractingWithBoundingBox
    ) {
      handleCloseModal();
    }
  };

  useEffect(() => {
    const handleEscapeKey = (event) => {
      if (event.key === "Escape") {
        handleCloseModal();
      }
    };
    document.addEventListener("keydown", handleEscapeKey);
    return () => {
      document.removeEventListener("keydown", handleEscapeKey);
    };
  }, [handleCloseModal]);

  return (
    <div
      className={styles.modal}
      ref={modalBackgroundRef}
      onClick={handleClickOutside}
    >
      <ToastContainer
        position="top-center"
        autoClose={3000}
        hideProgressBar
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="colored"
      />
      {annotateMode && (
        <>
          <div
            className={styles.navOverlayLeft}
            onClick={(e) => {
              e.stopPropagation();
              onPrevImage();
            }}
          >
            <span className={styles.arrow}>&larr;</span>
          </div>
          <div
            className={styles.navOverlayRight}
            onClick={(e) => {
              e.stopPropagation();
              onNextImage();
            }}
          >
            <span className={styles.arrow}>&rarr;</span>
          </div>
        </>
      )}
      <div className={styles["modal-content"]} ref={modalRef}>
        <div className={styles["modal-image-container"]}>
          <img
            ref={imageRef}
            src={imageUrl}
            alt={`ID: ${selectedImage}`}
            onLoad={() => {
              const { naturalWidth, naturalHeight } = imageRef.current;
              setNaturalSize({ width: naturalWidth, height: naturalHeight });
              if (imageRef.current) {
                const { width, height } =
                  imageRef.current.getBoundingClientRect();
                setImageSize({ width, height });
              }
            }}
            className={styles["modal-image"]}
            onDragStart={(e) => e.preventDefault()}
          />
          {imageSize.width > 0 &&
            imageSize.height > 0 &&
            boxes.map((box) => (
              <BoundingBox
                key={box.id}
                id={box.id}
                imageWidth={naturalSize.width}
                imageHeight={naturalSize.height}
                renderWidth={imageSize.width}
                renderHeight={imageSize.height}
                onBoxChange={(newBoxData) =>
                  handleBoxChange(newBoxData, box.id)
                }
                initialBox={box}
                onRemove={() => handleRemoveBox(box.id)}
                showRemoveButton={true}
                setIsInteractingWithBoundingBox={
                  setIsInteractingWithBoundingBox
                }
                classList={filteredClassList}
              />
            ))}
        </div>
        <div className={styles["modal-controls"]}>
          <button
            className={`${styles["control-button"]} ${styles["add-button"]}`}
            onClick={handleAddBox}
          >
            Add Box
          </button>
          <button
            className={`${styles["control-button"]} ${styles["save-button"]}`}
            onClick={handleSave}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

export default Modal;
