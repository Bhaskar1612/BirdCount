import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';

// List Page: shows gallery of images and navigates to detail view with state

export default function ActiveLearningBirdcount() {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();


  // Read limit from query params or default to 5
  const limitParam = searchParams.get('limit');
  const limit = [5, 10, 20].includes(Number(limitParam)) ? Number(limitParam) : 5;

  useEffect(() => {
    async function fetchImages() {
      setLoading(true);
      setError(null);
      try {
        const base = process.env.REACT_APP_API_BASE_URL;
        const params = new URLSearchParams({
          task: 'bird-count',
          page: 'active-learning-birdcount',
          limit: String(limit)
        });
        const res = await fetch(`${base}/images?${params.toString()}`, {
          credentials: 'include'
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const data = await res.json();
        setImages(data);
      } catch (err) {
        console.error(err);
        setError('Failed to load images');
      } finally {
        setLoading(false);
      }
    }
    fetchImages();
  }, [limit]);

  if (loading) return <div className="p-4">Loading images...</div>;
  if (error) return <div className="p-4 text-red-500">{error}</div>;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Active Learning: Bird Count</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {images.map((img) => (
          <div
            key={img.image_id}
            className="border rounded-lg overflow-hidden shadow-sm cursor-pointer"
            onClick={() =>
              navigate('/active-learning-birdcount/detail', {
                state: {
                  image: img,
                  boxes: img.boxes
                }
              })
            }
          >
            <img
              src={`${process.env.REACT_APP_API_BASE_URL}/images?task=bird-count&image_id=${img.image_id}`}
              alt={`Image ${img.image_id}`}
              className="w-full h-48 object-cover"
              crossOrigin="use-credentials"
            />
            <div className="p-2">
              <p className="text-sm">Image ID: {img.image_id}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}