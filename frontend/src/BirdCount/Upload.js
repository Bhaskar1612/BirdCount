import React, { useState } from 'react';
import './Upload.css';
import { useNavigate } from 'react-router-dom';
import {  useEffect } from "react";

import { Link } from 'react-router-dom';
import Header from '../Common/Header';
import axiosInstance from './api.js';

const cloneFormData = (formData) => {
  const cloned = new FormData();
  for (let [key, value] of formData.entries()) {
    cloned.append(key, value);
  }
  return cloned;
};
function Upload() {

  const [originalImage, setOriginalImage] = useState(null);
  const [originalFile, setOriginalFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [count,setCount] = useState(null);
  const [gridMap,setGridMap] = useState([]);
  const [imageID,setImageID] = useState(null);
  const [userID,setUserID] = useState(null);
  const [clusterMap, setClusterMap] = useState([]);
  const navigate = useNavigate();
  
  useEffect(() => {
  console.log(imageID, userID); // This will log updated values
}, [imageID, userID]);

  const handleImageUpload = async(event) => {
    console.log(process.env.REACT_APP_API_BASE_URL)
    const file = event.target.files[0];
    if (file) {
      setOriginalImage(URL.createObjectURL(file)); // Set original image for display
      setOriginalFile(file);

      // Create form data to send the image
      const formData = new FormData();
      formData.append('file', file);
  
    try {
      
      // Send image to FastAPI endpoint
      const resultImageResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL}/model_heatmap/`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });


      if (!resultImageResponse.ok) {
        throw new Error("Failed to fetch processed image");
      }

      const blob = await resultImageResponse.blob();
      const resultImageUrl = URL.createObjectURL(blob); // Convert blob to URL
      setResultImage(resultImageUrl); // Set result image for display

      // Call the fetch functions
      const countData = await fetchModelCount(cloneFormData(formData));
      const gridMap = await fetchModelArray(cloneFormData(formData));
      const data1 = await fetchImageId(cloneFormData(formData));


      // Update state if needed
      setCount(countData);
      setGridMap(gridMap); // Update the state with fetched gridMap
      setImageID(data1[0]);
      setUserID(data1[1]);


      fetch(`${process.env.REACT_APP_API_BASE_URL}/model_cluster/`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      })
        .then((response) => response.json())
        .then((data) => {
          // Assuming the API returns an array of { x, y } points
          setClusterMap(data || []);
          console.log(data)
          handleSave(data1[0],data);
        })
        .catch((error) => console.error('Error fetching cluster map:', error));

    } catch (error) {
      console.error('Error processing image:', error);
    }
    
  }
};

const fetchImageId = async (formData) => {
  formData.append('type', 'image');
  formData.append('task', 'bird-count');   
  formData.append('consent', true);   
  try {
    const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error("Failed to add image to database");
    }
    const data = await response.json();
    console.log("imageID:", data); 
    formData.append('image_id',data['uploaded_image_ids'][0] );
    const boxesRes = await fetch(
      `${process.env.REACT_APP_API_BASE_URL}/active-learning/auto-boxes/`,
      {
        method: 'POST',
        body: formData,
        credentials: 'include',
      }
    );
    if (!boxesRes.ok) {
      console.warn(
        'Auto‑boxes generation call failed:',
        await boxesRes.text()
      );
    } 
    else {
      console.log('Auto‑boxes request sent successfully');
    }
    return [data['uploaded_image_ids'][0],data['user_id']];

  } catch (error) {
    console.error('Error adding image to database:', error);
    return -1;
  }
  
  
}

  const handleSave = async (id,clusterCenters) => {
    console.log(id);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/annotations?image_id=${id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(clusterCenters),
        credentials: 'include',
      });

      if (response.status === 200) {
        
      } else {
        const errorData = await response.json();
        console.error('Error saving changes:', errorData.detail);
        
      }
    } catch (error) {
      console.error('Error:', error);
      alert('An error occurred while saving changes.');
    }
  };


const fetchModelCount = async (formData) => {
  
  try {
    const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/model_count/`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });



    if (!response.ok) {
      throw new Error("Failed to fetch model count");
    }

    


    const data = await response.json();
    console.log("Model Count Data:", data); // Log count data for inspection
    return data; // Return the count data
  } catch (error) {
    console.error('Error fetching model count:', error);
    return { count: 0 }; // Return a default value in case of error
  }
  
  
};

  // Fetch model array from API
const fetchModelArray = async (formData) => {
  try {
    const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/model_gridmap/`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error("Failed to fetch model array");
    }

    const data = await response.json();
    console.log("Model Array Data:", data); // Log the data for inspection

    return data; // Return the array
  } catch (error) {
    console.error('Error fetching model array:', error);
    return []; // Return an empty array in case of error
  }
};

  return (
    <div>
      <Header/>
    <div className="upload-container">
      
      <div className="upload-box">
      <h2>Welcome to <span>Bird Count</span></h2>
      <p class="text-xs">Our platform leverages advanced deep learning to count birds for ecological research accurately. Bird Count aids researchers in efficient data collection, supporting vital bird population monitoring.</p>
      {!count && (<p class="text-xs">Upload your image to get the count. <br></br>This is a research project at IIITD. If you upload an image, it will not be saved by us.</p>)}
      <input id="file-upload" type="file" accept="image/*" onChange={handleImageUpload} style={{ display: 'none' }}/>
      <label htmlFor="file-upload" className="custom-upload-button">
        Upload Image
      </label>
      {count !==null && (
    <h3>Total Count = {Math.floor(count)} +- {(count - Math.floor(count)).toFixed(2)} </h3>
  )}
      <div className="image-display">
  {originalImage && (
    <div className="image-container">
      <h4>Original Image (3x3 Grid)</h4>
      <div className="grid-container">
        <img src={originalImage} alt="Original" className="grid-image" />
        <div className="grid-overlay">
          <div></div><div></div><div></div>
          <div></div><div></div><div></div>
          <div></div><div></div><div></div>
        </div>
      </div>
    </div>
  )}
  {resultImage && (
    <div className="image-container">
      <h4>Processed Image</h4>
      <img src={resultImage} alt="Processed" />
    </div>
  )}
  {gridMap && gridMap.length>0 && (
  <div className="number-grid-container">
          <h4>Count Of Each Grid</h4>
          <div className="number-grid">
            {gridMap.map((number, index) => (
              <div key={index} className="number-cell">{number[0]} +- {number[1].toFixed(2)}</div>
            ))}
  </div>
  </div>
  )}
    </div>
    {originalImage && (
      <div>
        <h3>Help us improve the model</h3>
        <button className="custom-upload-button"><Link
          to={{
            pathname: '/annotate',
          }}
          state={{ file: originalFile,id:imageID}}
        >
          Go to Annotate
        </Link></button>
        
      </div>
      )}
      <div>
         <button className="custom-upload-button"><Link
          to={{
            pathname: '/gallery',
          }}
        >
          Your Gallery
        </Link></button>
      </div>
      </div>
      
    </div>
    </div>
  );
}

export default Upload;