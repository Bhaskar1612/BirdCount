import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Link } from 'react-router-dom';
import "./Gallery.css";

const Gallery = () => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchImages = async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_API_BASE_URL}/images?task=bird-count`,
          { credentials: "include" }
        );
        const data = await response.json();
        setImages(data.images || []);
      } catch (error) {
        console.error("Error fetching images:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchImages();
  }, []);

  const handleImageClick = async (image) => {
    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE_URL}/images?task=bird-count&image_id=${image.id}`,
        { credentials: "include" }
      );
      const blob = await response.blob();
      const file = new File([blob], `image_${image.id}.jpg`, { type: blob.type });

      navigate("/annotate", { state: { id: image.id, file } });
    } catch (error) {
      console.error("Error fetching image file:", error);
    }
  };

  return (
    <div className="gallery-container">
      <h2>My Image Gallery</h2>
      {loading ? (
        <p>Loading...</p>
      ) : images.length === 0 ? (
        <p>No images found.</p>
      ) : (
        <div className="image-grid">
          {images.map((image) => (
            <div key={image.id} className="image-card" onClick={() => handleImageClick(image)}>
              <img
                src={`${process.env.REACT_APP_API_BASE_URL}/images?task=bird-count&image_id=${image.id}`}
                alt={`Image ${image.id}`}
                crossOrigin="use-credentials"
              />
            </div>
          ))}
        </div>
      )}
      <div>
         <button className="custom-upload-button"><Link
          to={{
            pathname: '/upload',
          }}
        >
          Upload New
        </Link></button>
      </div>
    </div>
  );
};

export default Gallery;
