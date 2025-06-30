import React, { useCallback, useEffect, useRef, useState } from "react";
import Select from "react-select";
import styles from "./styles.module.css";

const MIN_WIDTH = 100;
const MIN_HEIGHT = 30;

const convertCenterToTopLeft = (xCenter, yCenter, width, height) => ({
  x: xCenter - width / 2,
  y: yCenter - height / 2,
  width,
  height,
});

const convertTopLeftToCenter = (xTopLeft, yTopLeft, width, height) => ({
  x: xTopLeft + width / 2,
  y: yTopLeft + height / 2,
  width,
  height,
});

const BoundingBox = ({
  id,
  imageWidth,
  imageHeight,
  renderWidth,
  renderHeight,
  onBoxChange,
  initialBox = null,
  onRemove,
  showRemoveButton,
  setIsInteractingWithBoundingBox,
  classList,
}) => {
  const filteredClassList = classList.filter(
    (cls) =>
      cls.name.trim().toLowerCase() !== "all" &&
      cls.name.trim().toLowerCase() !== "blan_blan"
  );

  // initialize the bounding box state (both new and existing boxes)
  const [boundingBox, setBoundingBox] = useState(() => {
    if (initialBox) {
      const reactCoords = convertCenterToTopLeft(
        initialBox.x,
        initialBox.y,
        initialBox.width,
        initialBox.height
      );
      const initialCategory =
        initialBox.class_id !== undefined &&
        filteredClassList.some((cls) => String(cls.id) === String(initialBox.class_id))
          ? initialBox.class_id
          : filteredClassList[0]?.id || null;
      return {
        ...reactCoords,
        category: initialCategory,
      };
    }
    const defaultCategory = filteredClassList[0]?.id || null;
    return { x: 10, y: 10, width: 100, height: 100, category: defaultCategory };
  });

  // states for drag and resize actions
  const [isDragging, setDragging] = useState(false);
  const [isResizing, setResizing] = useState(false);
  const [currentResizeHandle, setResizeHandle] = useState("");
  const [renderSize, setRenderSize] = useState({
    width: imageWidth,
    height: imageHeight,
  });

  // refs to track the DOM element and mouse interactions
  const boxRef = useRef(null);
  const selectRef = useRef(null);
  const initialBoxRef = useRef(boundingBox);
  const startPositionRef = useRef({ x: 0, y: 0 });
  const lastBoxUpdateRef = useRef(boundingBox);

  // scale factors between image and rendered sizes
  const scaleX = renderWidth / imageWidth;
  const scaleY = renderHeight / imageHeight;

  // handle the start of a drag action on the bounding box
  const handleDragStart = useCallback(
    (e) => {
      if (e.target === boxRef.current) {
        e.preventDefault();
        e.stopPropagation();
        const { clientX, clientY } = e;
        const { left, top } = boxRef.current.getBoundingClientRect();
        startPositionRef.current = {
          x: (clientX - left) / scaleX,
          y: (clientY - top) / scaleY,
        };
        setDragging(true);
        setIsInteractingWithBoundingBox(true);
      }
    },
    [setIsInteractingWithBoundingBox, scaleX, scaleY]
  );

  // initialize a resize action with one of the resize handles
  const handleResizeInitiate = useCallback(
    (e, handle) => {
      e.preventDefault();
      e.stopPropagation();
      const { clientX, clientY } = e;
      startPositionRef.current = { x: clientX, y: clientY };
      // save the initial bounding box state before resizing
      initialBoxRef.current = boundingBox;
      setResizing(true);
      setResizeHandle(handle);
      setIsInteractingWithBoundingBox(true);
    },
    [boundingBox, setIsInteractingWithBoundingBox]
  );

  // handle mouse movement for both dragging and resizing
  const handleMovement = useCallback(
    (e) => {
      e.preventDefault();
      const scaleX = renderSize.width / imageWidth;
      const scaleY = renderSize.height / imageHeight;

      if (isDragging) {
        // calculate new position based on mouse movement
        const { clientX, clientY } = e;
        const { left, top } = boxRef.current.parentElement.getBoundingClientRect();
        let newX = (clientX - left) / scaleX - startPositionRef.current.x;
        let newY = (clientY - top) / scaleY - startPositionRef.current.y;

        // clamp the coordinates so the box remains within the image bounds
        newX = Math.max(0, Math.min(newX, imageWidth - boundingBox.width));
        newY = Math.max(0, Math.min(newY, imageHeight - boundingBox.height));

        setBoundingBox((prevBox) => ({ ...prevBox, x: newX, y: newY }));
      } else if (isResizing) {
        // calculate the change in mouse coordinates since resize started
        const { clientX, clientY } = e;
        const dx = (clientX - startPositionRef.current.x) / scaleX;
        const dy = (clientY - startPositionRef.current.y) / scaleY;

        setBoundingBox(() => {
          const startingBox = initialBoxRef.current;
          let updatedBox = { ...startingBox };

          // update box dimensions according to the active resize handle
          switch (currentResizeHandle) {
            case "nw": {
              // resize from top-left corner
              const minDx = -startingBox.x;
              const maxDx = startingBox.width - MIN_WIDTH;
              const effectiveDx = Math.min(Math.max(dx, minDx), maxDx);

              const minDy = -startingBox.y;
              const maxDy = startingBox.height - MIN_HEIGHT;
              const effectiveDy = Math.min(Math.max(dy, minDy), maxDy);

              updatedBox.x = startingBox.x + effectiveDx;
              updatedBox.y = startingBox.y + effectiveDy;
              updatedBox.width = startingBox.width - effectiveDx;
              updatedBox.height = startingBox.height - effectiveDy;
              break;
            }
            case "ne": {
              // resize from top-right corner
              const minDx = MIN_WIDTH - startingBox.width;
              const maxDx = imageWidth - (startingBox.x + startingBox.width);
              const effectiveDx = Math.min(Math.max(dx, minDx), maxDx);

              const minDy = -startingBox.y;
              const maxDy = startingBox.height - MIN_HEIGHT;
              const effectiveDy = Math.min(Math.max(dy, minDy), maxDy);

              updatedBox.y = startingBox.y + effectiveDy;
              updatedBox.width = startingBox.width + effectiveDx;
              updatedBox.height = startingBox.height - effectiveDy;
              break;
            }
            case "sw": {
              // resize from bottom-left corner
              const minDx = -startingBox.x;
              const maxDx = startingBox.width - MIN_WIDTH;
              const effectiveDx = Math.min(Math.max(dx, minDx), maxDx);

              const minDy = MIN_HEIGHT - startingBox.height;
              const maxDy = imageHeight - (startingBox.y + startingBox.height);
              const effectiveDy = Math.min(Math.max(dy, minDy), maxDy);

              updatedBox.x = startingBox.x + effectiveDx;
              updatedBox.width = startingBox.width - effectiveDx;
              updatedBox.height = startingBox.height + effectiveDy;
              break;
            }
            case "se": {
              // resize from bottom-right corner
              const minDx = MIN_WIDTH - startingBox.width;
              const maxDx = imageWidth - (startingBox.x + startingBox.width);
              const effectiveDx = Math.min(Math.max(dx, minDx), maxDx);

              const minDy = MIN_HEIGHT - startingBox.height;
              const maxDy = imageHeight - (startingBox.y + startingBox.height);
              const effectiveDy = Math.min(Math.max(dy, minDy), maxDy);

              updatedBox.width = startingBox.width + effectiveDx;
              updatedBox.height = startingBox.height + effectiveDy;
              break;
            }
            default:
              break;
          }

          // ensure the updated box does not exceed image bounds
          updatedBox.x = Math.max(0, Math.min(updatedBox.x, imageWidth - updatedBox.width));
          updatedBox.y = Math.max(0, Math.min(updatedBox.y, imageHeight - updatedBox.height));
          updatedBox.width = Math.min(updatedBox.width, imageWidth - updatedBox.x);
          updatedBox.height = Math.min(updatedBox.height, imageHeight - updatedBox.y);

          return updatedBox;
        });
      }
    },
    [isDragging, isResizing, currentResizeHandle, imageWidth, imageHeight, renderSize]
  );

  // finalize the drag or resize action on mouse release
  const handleMouseRelease = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      setResizing(false);
      setTimeout(() => setIsInteractingWithBoundingBox(false), 50);
    },
    [setIsInteractingWithBoundingBox]
  );

  // register mouse events when dragging or resizing
  useEffect(() => {
    if (isDragging || isResizing) {
      document.addEventListener("mousemove", handleMovement);
      document.addEventListener("mouseup", handleMouseRelease);
    }
    return () => {
      document.removeEventListener("mousemove", handleMovement);
      document.removeEventListener("mouseup", handleMouseRelease);
    };
  }, [isDragging, isResizing, handleMovement, handleMouseRelease]);

  // update the parent component when the bounding box state changes
  useEffect(() => {
    if (
      boundingBox.x !== lastBoxUpdateRef.current.x ||
      boundingBox.y !== lastBoxUpdateRef.current.y ||
      boundingBox.width !== lastBoxUpdateRef.current.width ||
      boundingBox.height !== lastBoxUpdateRef.current.height ||
      boundingBox.category !== lastBoxUpdateRef.current.category
    ) {
      lastBoxUpdateRef.current = boundingBox;
      const yoloCoords = convertTopLeftToCenter(
        boundingBox.x,
        boundingBox.y,
        boundingBox.width,
        boundingBox.height
      );
      onBoxChange({
        ...yoloCoords,
        category: boundingBox.category,
      });
    }
  }, [boundingBox, onBoxChange]);

  // handle changes to the object class selection
  const handleCategoryChange = useCallback((selectedOption) => {
    setBoundingBox((prevBox) => ({
      ...prevBox,
      category: selectedOption.value,
    }));
  }, []);

  // update the render size on window resize
  useEffect(() => {
    const updateRenderSize = () => {
      if (boxRef.current && boxRef.current.parentElement) {
        const { width, height } = boxRef.current.parentElement.getBoundingClientRect();
        setRenderSize({ width, height });
      }
    };

    updateRenderSize();
    window.addEventListener("resize", updateRenderSize);
    return () => window.removeEventListener("resize", updateRenderSize);
  }, [imageWidth, imageHeight]);

  const fontSize = Math.max(10, initialBox.width * (renderWidth / imageWidth) / 20);
  return (
    <div
      ref={boxRef}
      className={styles["bounding-box"]}
      style={{
        left: `${boundingBox.x * scaleX}px`,
        top: `${boundingBox.y * scaleY}px`,
        width: `${boundingBox.width * scaleX}px`,
        height: `${boundingBox.height * scaleY}px`,
      }}
      onMouseDown={handleDragStart}
    >
      <div className={styles["class-label-container"]}>
        <Select
          ref={selectRef}
          options={filteredClassList.map((cls) => ({
            value: cls.id,
            label: cls.name,
          }))}
          value={{
            value: boundingBox.category,
            label:
              filteredClassList.find(
                (cls) => String(cls.id) === String(boundingBox.category)
              )?.name || filteredClassList[0]?.name,
          }}
          onChange={handleCategoryChange}
          className={styles["category-select"]}
          classNamePrefix="select"
          isSearchable
          onMouseDown={(e) => e.stopPropagation()}
          styles={{
            control: (provided) => ({
              ...provided,
              fontSize: `${fontSize}px`,
            }),
            singleValue: (provided) => ({
              ...provided,
              fontSize: `${fontSize}px`,
              whiteSpace: "normal",
            }),
          }}
        />
      </div>
      {showRemoveButton && (
        <button
          className={styles["remove-button"]}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          ×
        </button>
      )}
      <div
        className={`${styles["resize-handle"]} ${styles["nw"]}`}
        onMouseDown={(e) => handleResizeInitiate(e, "nw")}
      />
      <div
        className={`${styles["resize-handle"]} ${styles["ne"]}`}
        onMouseDown={(e) => handleResizeInitiate(e, "ne")}
      />
      <div
        className={`${styles["resize-handle"]} ${styles["sw"]}`}
        onMouseDown={(e) => handleResizeInitiate(e, "sw")}
      />
      <div
        className={`${styles["resize-handle"]} ${styles["se"]}`}
        onMouseDown={(e) => handleResizeInitiate(e, "se")}
      />
      {/* <div className={styles["debug-info"]} style={{ position: 'absolute', top: 0, left: 0, background: 'rgba(255,255,255,0.7)', padding: '5px', fontSize: '12px' }}>
        <p><strong>Box Position:</strong> x: {boundingBox.x.toFixed(2)}, y: {boundingBox.y.toFixed(2)}</p>
        <p><strong>Box Size:</strong> width: {boundingBox.width.toFixed(2)}, height: {boundingBox.height.toFixed(2)}</p>
        <p><strong>Image Size:</strong> width: {imageWidth}, height: {imageHeight}</p>
        <p><strong>Rendered Size:</strong> width: {renderSize.width.toFixed(2)}, height: {renderSize.height.toFixed(2)}</p>
        { (boundingBox.x < 0 || boundingBox.y < 0 || boundingBox.x + boundingBox.width > imageWidth || boundingBox.y + boundingBox.height > imageHeight) && (
          <p style={{ color: 'red' }}>Warning: Bounding box is out of image bounds!</p>
        )}
      </div> */}
    </div>
  );
};

export default BoundingBox;