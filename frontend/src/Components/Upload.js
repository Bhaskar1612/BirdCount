import React, { useState } from 'react';
import './Upload.css';

function Upload() {
  const [imageSrc, setImageSrc] = useState(null);
  const [prediction, setPrediction] = useState("");

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImageSrc(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

    const handleSubmit = async (e) => {
        e.preventDefault(); 
        const formData = new FormData();
        formData.append('file', imageSrc);

        const response = await fetch('http://localhost:8000/model/', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        setPrediction(result.prediction);
    };

  return (
    <div className="upload-container">
      <h2 className="upload-title">Upload Image</h2>
      <input type="file" accept="image/*" onChange={handleImageUpload} className="upload-input" />
      {imageSrc && (
        <div className="image-display fullscreen">
          <img src={imageSrc} alt="Uploaded" className="uploaded-image" />
          <img src={imageSrc} alt="Uploaded" className="uploaded-image" />
        </div>
      )}
    </div>
  );
}

export default Upload;
