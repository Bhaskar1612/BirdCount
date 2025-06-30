import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Rnd } from 'react-rnd';
import './Annotate.css';
import Header from '../Common/Header';

function Annotate() {
  const { state } = useLocation();
  const navigate = useNavigate();

  // Persist image ID and URL in localStorage
  const [imageUrl, setImageUrl] = useState(() => localStorage.getItem('annotateImageUrl'));
  const [currentImageID, setCurrentImageID] = useState(() => localStorage.getItem('annotateImageID'));

  // Annotations and boxes
  const [clusterMap, setClusterMap] = useState([]);
  const [mode, setMode] = useState('dots');
  const [boxes, setBoxes] = useState([]);

  // Selection rectangle for cropping (dot mode)
  const [selRect, setSelRect] = useState(null);

  const imageRef = useRef(null);

  // On state change (file + id), update localStorage
  useEffect(() => {
    const { file, id } = state || {};
    if (file && id) {
      const url = URL.createObjectURL(file);
      localStorage.setItem('annotateImageUrl', url);
      localStorage.setItem('annotateImageID', id.toString());
      setImageUrl(url);
      setCurrentImageID(id.toString());
    }
  }, [state]);

  // Fetch initial dots when image ID is set
  useEffect(() => {
    if (!currentImageID) return;
    fetch(`${process.env.REACT_APP_API_BASE_URL}/annotations?image_id=${currentImageID}`, {
      method: 'GET', credentials: 'include'
    })
      .then(res => res.json())
      .then(data => setClusterMap(data.annotations || []))
      .catch(console.error);
  }, [currentImageID]);

  // Dot mode: add a point
  const handleImageClick = e => {
    if (mode !== 'dots' || !imageRef.current) return;
    const rect = imageRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setClusterMap(prev => [...prev, { x, y }]);
  };

  // Dot mode: remove a point
  const handleDotClick = index => {
    if (mode !== 'dots') return;
    setClusterMap(prev => prev.filter((_, i) => i !== index));
  };

  // Save all dots
  const handleSave = async () => {
    if (!currentImageID) return;
    try {
      const res = await fetch(
        `${process.env.REACT_APP_API_BASE_URL}/annotations?image_id=${currentImageID}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(clusterMap)
        }
      );
      if (res.ok) alert('Changes saved!');
      else {
        const err = await res.json();
        alert('Save failed: ' + (err.detail || res.statusText));
      }
    } catch (err) {
      console.error(err);
      alert('Error saving.');
    }
  };

  // Dot mode: crop and pass dots
  const cropDots = () => {
    if (!selRect || selRect.width === 0) {
      alert('Select a region first.');
      return;
    }
    // --- Annotate.js (inside your cropDots)
  navigate('/region-view', {
    state: {
      imageUrl,
      currentImageID,
      selectionRect: selRect,
      scaleFactor: 10,
      displayedImageWidth: imageRef.current.clientWidth,
      displayedImageHeight: imageRef.current.clientHeight,
     clusterMap,          
    }
  });

  };

  // Box mode: add a single box
  const addBox = () => {
    if (!imageRef.current) return;
    const w = 100, h = 100;
    const x = (imageRef.current.clientWidth - w) / 2;
    const y = (imageRef.current.clientHeight - h) / 2;
    setBoxes([{ x, y, width: w, height: h }]);
  };

  const updateBox = (i, newBox) => {
    setBoxes(prev => prev.map((b, idx) => (idx === i ? newBox : b)));
  };

  const cropBox = () => {
    if (!boxes.length) {
      alert('Add box first.');
      return;
    }
    const box = boxes[0];
    navigate('/region-view', {
      state: {
        imageUrl,
        currentImageID,
        selectionRect: box,
        scaleFactor: 10,
        displayedImageWidth: imageRef.current.clientWidth,
        displayedImageHeight: imageRef.current.clientHeight,
        clusterMap
      }
    });
  };

  // Attach only dot-mode events to container
  const containerProps =
    mode === 'dots'
      ? { onClick: handleImageClick }
      : {};

  return (
    <div>
      <Header />
      <div className="annotation-controls">
        <button onClick={() => setMode('dots')} disabled={mode === 'dots'}>
          Dot Mode
        </button>
        <button onClick={() => setMode('box')} disabled={mode === 'box'}>
          Box Mode
        </button>
        {mode === 'box' && (
          <button onClick={addBox} disabled={boxes.length > 0}>
            {boxes.length ? 'Box Added' : 'Add Box'}
          </button>
        )}
      </div>

      <div className="annotation-container">
        <h2>Annotation ({mode.toUpperCase()})</h2>
        {imageUrl && (
          <div
            className="image-2-container"
            style={{ position: 'relative', display: 'inline-block' }}
            {...containerProps}
          >
            <img
              ref={imageRef}
              src={imageUrl}
              alt="Annotate"
              className="large-image"
            />

            {/* Dot overlay (interactive only in dot mode) */}
            <svg
              className="overlay"
              width="100%"
              height="100%"
              style={{ position: 'absolute', top: 0, left: 0 }}
            >
              {clusterMap.map((pt, i) => (
                <rect
                  key={i}
                  x={pt.x}
                  y={pt.y}
                  width={1}
                  height={1}
                  fill="blue"
                  style={{
                    cursor: mode === 'dots' ? 'pointer' : 'default',
                    pointerEvents: mode === 'dots' ? 'auto' : 'none'
                  }}
                  onClick={e => {
                    if (mode === 'dots') {
                      e.stopPropagation();
                      handleDotClick(i);
                    }
                  }}
                />
              ))}
            </svg>

            {/* Box mode: render draggable box */}
            {mode === 'box' &&
              boxes.map((box, i) => (
                <Rnd
                  key={i}
                  bounds="parent"
                  size={{ width: box.width, height: box.height }}
                  position={{ x: box.x, y: box.y }}
                  onDragStop={(e, d) => updateBox(i, { ...box, x: d.x, y: d.y })}
                  onResizeStop={(e, dir, ref, delta, pos) =>
                    updateBox(i, {
                      x: pos.x,
                      y: pos.y,
                      width: parseInt(ref.style.width, 10),
                      height: parseInt(ref.style.height, 10)
                    })
                  }
                  enableResizing={{
                    top: true,
                    right: true,
                    bottom: true,
                    left: true,
                    topRight: true,
                    bottomRight: true,
                    bottomLeft: true,
                    topLeft: true
                  }}
                >
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      border: '2px solid red',
                      boxSizing: 'border-box'
                    }}
                  />
                </Rnd>
              ))}

            {/* Dot mode: render selection rectangle */}
            {mode === 'dots' && selRect && (
              <div
                style={{
                  position: 'absolute',
                  border: '2px dashed red',
                  backgroundColor: 'rgba(255,0,0,0.2)',
                  left: selRect.x,
                  top: selRect.y,
                  width: selRect.width,
                  height: selRect.height,
                  pointerEvents: 'none'
                }}
              />
            )}
          </div>
        )}

        <div className="action-buttons">
          <button className="save-button" onClick={handleSave}>
            Save Annotations
          </button>
          {mode === 'dots' && selRect?.width > 0 && (
            <button className="crop-button" onClick={cropDots}>
              Crop & Enlarge
            </button>
          )}
          {mode === 'box' && boxes.length > 0 && (
            <button className="crop-button" onClick={cropBox}>
              Crop & Enlarge Box
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default Annotate;