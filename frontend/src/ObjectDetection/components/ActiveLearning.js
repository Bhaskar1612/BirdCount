import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Collage from "./Collage";
import Modal from "./Modal";
import styles from "./styles.module.css";
import {
  getActiveLearningImages,
  getImageUrl,
  getClasses,
} from "../api/imageApi";
import { logError } from "../utils/error.js";
import Header from "../../Common/Header.js";

const ActiveLearning = () => {
  const [images, setImages] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [columnImages, setColumnImages] = useState([[], [], [], [], []]);
  const [classList, setClassList] = useState([]);
  const navigate = useNavigate();
  const [numImages, setNumImages] = useState(5);
  const [selectionResetCounter, setSelectionResetCounter] = useState(0);
  const [isSingleAnnotation, setIsSingleAnnotation] = useState(false);

  const annotationListRef = useRef({ head: null, tail: null });

  const listToArray = () => {
    const arr = [];
    const { head } = annotationListRef.current;
    if (!head) return arr;
    let curr = head;
    do {
      arr.push(curr.id);
      curr = curr.next;
    } while (curr !== head);
    return arr;
  };

  const addNode = (id) => {
    const currArr = listToArray();
    if (currArr.includes(id)) return;
    const newNode = { id, next: null, prev: null };
    const list = annotationListRef.current;
    if (!list.head) {
      newNode.next = newNode;
      newNode.prev = newNode;
      list.head = newNode;
      list.tail = newNode;
    } else {
      const tail = list.tail;
      newNode.prev = tail;
      newNode.next = list.head;
      tail.next = newNode;
      list.head.prev = newNode;
      list.tail = newNode;
    }
  };

  const removeNode = (id) => {
    const list = annotationListRef.current;
    if (!list.head) return;
    let curr = list.head;
    let found = false;
    do {
      if (curr.id === id) {
        found = true;
        break;
      }
      curr = curr.next;
    } while (curr !== list.head);

    if (!found) return;

    const isLastNode = curr.next === curr;
    const wasSelected = selectedImage === id;

    if (isLastNode) {
      list.head = null;
      list.tail = null;
    } else {
      curr.prev.next = curr.next;
      curr.next.prev = curr.prev;
      if (curr === list.head) {
        list.head = curr.next;
      }
      if (curr === list.tail) {
        list.tail = curr.prev;
      }
    }

    if (wasSelected && !isSingleAnnotation) {
      if (isLastNode) {
        setSelectedImage(null);
      } else {
        setSelectedImage(curr.next.id);
      }
    } else if (wasSelected && isSingleAnnotation) {
      setSelectedImage(null);
    }
  };

  const updateAnnotationSelection = (newSelectedIds) => {
    const current = listToArray();
    for (const id of current) {
      if (!newSelectedIds.includes(id)) {
        removeNode(id);
      }
    }
    for (const id of newSelectedIds) {
      if (!listToArray().includes(id)) {
        addNode(id);
      }
    }
    if (!annotationListRef.current.head && !isSingleAnnotation) {
      setSelectedImage(null);
    }
  };

  useEffect(() => {
    const availableIds = images.map((img) => img.id);
    const current = listToArray();
    current.forEach((id) => {
      if (!availableIds.includes(id)) {
        removeNode(id);
      }
    });
  }, [images]);

  const loadImages = useCallback(async () => {
    try {
      const fetchedImages = await getActiveLearningImages(numImages);
      setImages(fetchedImages);
      distributeImages(fetchedImages);
    } catch (error) {
      logError("Error fetching active learning images:", error);
    }
  }, [numImages]);

  const distributeImages = useCallback(async (imageList) => {
    const columns = Array.from({ length: 5 }, () => []);
    for (let index = 0; index < imageList.length; index++) {
      const imageData = imageList[index];
      const columnIndex = index % 5;
      try {
        const src = await getImageUrl(imageData.id);
        columns[columnIndex].push({
          ...imageData,
          src: src,
        });
      } catch (error) {
        logError(`Error fetching image URL for image ${imageData.id}:`, error);
      }
    }
    setColumnImages(columns);
  }, []);

  const handleNumImagesChange = (event) => {
    setNumImages(parseInt(event.target.value, 10));
  };

  useEffect(() => {
    loadImages();
  }, [numImages, loadImages]);

  useEffect(() => {
    const fetchClasses = async () => {
      try {
        const fetchedClasses = await getClasses();
        setClassList(fetchedClasses);
      } catch (error) {
        logError("Error fetching classes:", error);
      }
    };
    fetchClasses();
  }, []);

  const handleDone = () => {
    const annotateMore = window.confirm("Do you want to annotate more images?");
    if (annotateMore) {
      loadImages();
      annotationListRef.current = { head: null, tail: null };
    } else {
      alert("Thank you for annotating!");
      navigate("/species-segregation");
    }
  };

  const handleAnnotate = () => {
    if (!annotationListRef.current.head) {
      alert("No images selected to annotate. Please select some images.");
      return;
    }
    setIsSingleAnnotation(false);
    setSelectedImage(annotationListRef.current.head.id);
  };

  const handleImageClick = (id) => {
    setIsSingleAnnotation(true);
    setSelectedImage(id);
  };

  const handleNextImage = useCallback(() => {
    const list = annotationListRef.current;
    if (!list.head) return;
    let curr = list.head;
    do {
      if (curr.id === selectedImage) break;
      curr = curr.next;
    } while (curr !== list.head);
    setSelectedImage(curr.next.id);
  }, [selectedImage]);

  const handlePrevImage = useCallback(() => {
    const list = annotationListRef.current;
    if (!list.head) return;
    let curr = list.head;
    do {
      if (curr.id === selectedImage) break;
      curr = curr.next;
    } while (curr !== list.head);
    setSelectedImage(curr.prev.id);
  }, [selectedImage]);

  return (
    <div className={styles["active-learning-page"]}>
      <Header activeLink="active-learning" />
      <main className={styles["active-learning-main"]}>
        <div className={styles["active-learning-options"]}>
          <div className={styles["active-learning-options-left"]}>
            <label
              htmlFor="numImages"
              className={styles["active-learning-label"]}
            >
              Number of Images to Annotate:
            </label>
            <select
              id="numImages"
              value={numImages}
              onChange={handleNumImagesChange}
              className={styles["active-learning-select"]}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>
          <div className={styles["active-learning-options-right"]}>
            <button
              className={styles["download-button"]}
              onClick={() => {
                annotationListRef.current = { head: null, tail: null };
                setSelectedImage(null);
                setSelectionResetCounter((prev) => prev + 1);
              }}
            >
              Clear All Selection
            </button>
          </div>
        </div>
        {images.length === 0 ? (
          <div className={styles["active-learning-empty-state"]}>
            <p>No images available right now. Please check back later.</p>
            <button
              className={styles["active-learning-cta-button"]}
              onClick={() => navigate("/species-segregation")}
            >
              Back to Home
            </button>
          </div>
        ) : (
          <>
            <Collage
              key={selectionResetCounter}
              columnImages={columnImages}
              handleImageClick={handleImageClick}
              activeLearning={true}
              onSelectionChange={updateAnnotationSelection}
            />
            {selectedImage && (
              <Modal
                selectedImage={selectedImage}
                handleCloseModal={() => setSelectedImage(null)}
                classList={classList}
                isForActiveLearning={true}
                annotateMode={true}
                onNextImage={!isSingleAnnotation ? handleNextImage : undefined}
                onPrevImage={!isSingleAnnotation ? handlePrevImage : undefined}
              />
            )}
            <div className={styles["active-learning-controls"]}>
              <button
                className={styles["active-learning-cta-button"]}
                onClick={handleDone}
              >
                Done
              </button>
              <button
                className={styles["active-learning-cta-button"]}
                onClick={handleAnnotate}
              >
                Annotate
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
};

export default ActiveLearning;
