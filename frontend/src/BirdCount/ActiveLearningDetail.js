import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';


// Detail Page: uses Canvas to overlay bounding boxes (coordinates match 480×384 canvas)
export function ActiveLearningBirdcountDetail() {
  const location = useLocation();
  const { image, boxes } = location.state || {};
  const canvasRef = useRef(null);

  // Canvas dimensions matching expected coordinate space
  const displayWidth = 480;
  const displayHeight = 384;

  useEffect(() => {
    if (!image || !boxes) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const imgEl = new Image();
    imgEl.crossOrigin = 'use-credentials';
    imgEl.src = `${process.env.REACT_APP_API_BASE_URL}/images?task=bird-count&image_id=${image.image_id}`;

    imgEl.onload = () => {
      // draw image at canvas size
      ctx.clearRect(0, 0, displayWidth, displayHeight);
      ctx.drawImage(imgEl, 0, 0, displayWidth, displayHeight);

      // draw each box directly (coords already match canvas)
      ctx.strokeStyle = 'lime';
      ctx.lineWidth = 2;
      boxes.forEach(({ x1, y1, x2, y2 }) => {
        ctx.strokeRect(
          x1,
          y1,
          x2 - x1,
          y2 - y1
        );
      });
    };
  }, [image, boxes]);

  if (!image || !boxes) {
    return <div className="p-4 text-red-500">No image data provided.</div>;
  }

  return (
    <div className="p-4 flex flex-col items-center">
      <h1 className="text-xl font-semibold mb-4">Image {image.image_id}</h1>
      <canvas
        ref={canvasRef}
        width={displayWidth}
        height={displayHeight}
        className="border rounded-md"
      />
    </div>
  );
}