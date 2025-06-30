import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import Header from '../Common/Header';

function RegionView() {
  const { state } = useLocation();
  const canvasRef = useRef(null);

  // Destructure passed state
  const {
    imageUrl,
    selectionRect,
    currentImageID,
    scaleFactor,
    displayedImageWidth,
    displayedImageHeight,
    clusterMap: initialMap = []
  } = state || {};

  // Local dot map state in cropped view
  const [clusterMap, setClusterMap] = useState(initialMap);
  const [isReady, setIsReady] = useState(false);

  // Draw function
  const redraw = () => {
    if (!imageUrl || !selectionRect || !canvasRef.current) return;
    const img = new Image();
    img.src = imageUrl;
    img.onload = () => {
      const canvas = canvasRef.current;
      canvas.width = selectionRect.width * scaleFactor;
      canvas.height = selectionRect.height * scaleFactor;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;

      // Upscaled crop
      const scaleX = img.naturalWidth / displayedImageWidth;
      const scaleY = img.naturalHeight / displayedImageHeight;
      const sx = selectionRect.x * scaleX;
      const sy = selectionRect.y * scaleY;
      const sw = selectionRect.width * scaleX;
      const sh = selectionRect.height * scaleY;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(
        img,
        sx,
        sy,
        sw,
        sh,
        0,
        0,
        selectionRect.width * scaleFactor,
        selectionRect.height * scaleFactor
      );

      // Draw existing dots
      ctx.fillStyle = 'white';
      clusterMap.forEach(pt => {
        if (
          pt.x >= selectionRect.x &&
          pt.x <= selectionRect.x + selectionRect.width &&
          pt.y >= selectionRect.y &&
          pt.y <= selectionRect.y + selectionRect.height
        ) {
          const dx = Math.round((pt.x - selectionRect.x) * scaleFactor);
          const dy = Math.round((pt.y - selectionRect.y) * scaleFactor);
          ctx.fillRect(dx, dy, 2, 2);
        }
      });
      setIsReady(true);
    };
  };

  // Initial and on-map change redraw
  useEffect(redraw, [imageUrl, selectionRect, scaleFactor, displayedImageWidth, displayedImageHeight, clusterMap]);

  // Handle clicks to toggle dots
  const handleCanvasClick = (e) => {
    if (!isReady) return;
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    // Map back to original coords
    const origX = selectionRect.x + cx / scaleFactor;
    const origY = selectionRect.y + cy / scaleFactor;
    // Check if any existing dot is at that original position (within .5px)
    const existingIndex = clusterMap.findIndex(pt =>
      Math.abs(pt.x - origX) < 0.5 && Math.abs(pt.y - origY) < 0.5
    );
    let newMap;
    if (existingIndex >= 0) {
      newMap = clusterMap.filter((_, i) => i !== existingIndex);
    } else {
      newMap = [...clusterMap, { x: origX, y: origY }];
    }
    setClusterMap(newMap);
  };

  // Save handler
  const handleSave = async () => {
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
      if (res.ok) alert('Annotations saved!');
      else alert('Save failed');
    } catch (err) {
      console.error(err);
      alert('Error saving');
    }
  };

  if (!imageUrl || !selectionRect) {
    return (
      <div>
        <Header />
        <p>Error: No image or region data provided.</p>
      </div>
    );
  }

  return (
    <div>
      <Header />
      <div style={{ textAlign: 'center', marginTop: '20px' }}>
        <h2>Scaled Region View</h2>
        <button onClick={handleSave} style={{ marginBottom: '10px' }}>Save Annotations</button>
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          style={{ border: '1px solid #ccc', cursor: 'crosshair' }}
        />
      </div>
    </div>
  );
}

export default RegionView;