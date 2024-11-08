import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import './Annotate.css';

function Annotate() {
  const { state } = useLocation();
  const { file } = state || {};
  const [focusLevel, setFocusLevel] = useState(1);
  const [clusterMap, setClusterMap] = useState([]);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const tensorShape = { width: 480, height: 384 }; // Tensor image dimensions
  const imageRef = useRef(null);

  // Load the image and set its URL and dimensions
  useEffect(() => {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      setImageUrl(URL.createObjectURL(file));

      // Create a new Image object to get the original dimensions
      const img = new Image();
      img.src = URL.createObjectURL(file);
      img.onload = () => {
        setImageDimensions({ width: img.width, height: img.height });
      };
    }
  }, [file]);

  // Fetch clustering data only once when the page loads
  useEffect(() => {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);

      fetch('http://127.0.0.1:8000/model_cluster/', {
        method: 'POST',
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => setClusterMap(data)) // Expecting data as array of lists with x-y dictionaries
        .catch((error) => console.error('Error fetching cluster map:', error));
    }
  }, [file]);

  // Get points for the selected focus level
  const pointsToHighlight = clusterMap[focusLevel - 1] || [];

  // Calculate scale factors based on the image's displayed size and original size
  const displayedWidth = imageRef.current?.clientWidth || 1;
  const displayedHeight = imageRef.current?.clientHeight || 1;

  const scaleX = displayedWidth / tensorShape.width;
  const scaleY = displayedHeight / tensorShape.height;

  // Set padding offsets
  const offsetX = 80; // Adjust this value to move dots horizontally
  const offsetY = 5; // Adjust this value to move dots vertically

  return (
    <div className="annotation-container">
      <h2>Annotation Page</h2>
      {imageUrl && (
        <div className="image-2-container">
          <img
            ref={imageRef}
            src={imageUrl}
            alt="Original"
            className="large-image"
          />
          <svg className="overlay" width={displayedWidth} height={displayedHeight}>
            {pointsToHighlight.map((point, index) => (
              <circle
                key={index}
                cx={point.x * scaleX + offsetX} // Apply scale to x-coordinate and add offset
                cy={point.y * scaleY + offsetY} // Apply scale to y-coordinate and add offset
                r="3" // Fixed radius for consistent dot size
                fill="blue"
              />
            ))}
          </svg>
        </div>
      )}

      {/* Slider */}
      <div className="slider-container">
        <label htmlFor="focus-level-slider">Focus Level: {focusLevel}</label>
        <input
          type="range"
          id="focus-level-slider"
          min="1"
          max="10"
          value={focusLevel}
          onChange={(e) => setFocusLevel(parseInt(e.target.value))}
        />
      </div>
    </div>
  );
}

export default Annotate;
