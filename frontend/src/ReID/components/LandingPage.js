import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './LandingPage.css';
import Header from "../../Common/Header.js";

const LandingPage = () => {
  const [selectedModel, setSelectedModel] = useState('megadescriptor');
  const [selectedSpecies, setSelectedSpecies] = useState('');
  const [speciesList, setSpeciesList] = useState([]);
  const [useGlobalGallery, setUseGlobalGallery] = useState(false);
  const [globalGalleryStatus, setGlobalGalleryStatus] = useState({ has_global_gallery: false, gallery_size: 0 });
  const [querySetFile, setQuerySetFile] = useState(null);
  const [gallerySetFile, setGallerySetFile] = useState(null);
  const [queryPreCropped, setQueryPreCropped] = useState(false);
  const [galleryPreCropped, setGalleryPreCropped] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [userConsent, setUserConsent] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [showSessions, setShowSessions] = useState(false);
  const [showGalleryManagement, setShowGalleryManagement] = useState(false);
  const [galleryPreview, setGalleryPreview] = useState([]);
  const [showSpeciesPreview, setShowSpeciesPreview] = useState(false);
  const [previewSpecies, setPreviewSpecies] = useState(null);
  const [previewImages, setPreviewImages] = useState([]);
  
  const navigate = useNavigate();
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

  // Fetch species list on component mount
  useEffect(() => {
    const fetchSpecies = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/reid/species`, {
          credentials: 'include'
        });
        
        if (response.ok) {
          const data = await response.json();
          setSpeciesList(data.species || []);
        }
      } catch (error) {
        console.error("Error fetching species:", error);
      }
    };
    
    fetchSpecies();
  }, [API_BASE_URL]);

  // Fetch user sessions
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/reid/sessions`, {
          credentials: 'include'
        });
        
        if (response.ok) {
          const data = await response.json();
          setSessions(data.sessions || []);
        }
      } catch (error) {
        console.error("Error fetching sessions:", error);
      }
    };
    
    fetchSessions();
  }, [API_BASE_URL]);

  // Check global gallery status when species is selected
  useEffect(() => {
    const checkGlobalGallery = async () => {
      if (selectedSpecies) {
        try {
          const response = await fetch(`${API_BASE_URL}/reid/global-gallery-status/${selectedSpecies}`, {
            credentials: 'include'
          });
          
          if (response.ok) {
            const data = await response.json();
            setGlobalGalleryStatus(data);
            
            // If no global gallery exists, force user to upload their own
            if (!data.has_global_gallery) {
              setUseGlobalGallery(false);
            }
          }
        } catch (error) {
          console.error("Error checking global gallery:", error);
        }
      }
    };
    
    checkGlobalGallery();
  }, [selectedSpecies, API_BASE_URL]);

  // COMMENTED OUT - PRIVACY FIX: Prevents display of non-consented global gallery images
  // Fetch gallery preview when species is selected
  // useEffect(() => {
  //   const fetchGalleryPreview = async () => {
  //     if (selectedSpecies) {
  //       try {
  //         const response = await fetch(`${API_BASE_URL}/reid/gallery-preview/${selectedSpecies}`, {
  //           credentials: 'include'
  //         });
  //         
  //         if (response.ok) {
  //           const data = await response.json();
  //           console.log('Gallery preview data received:', data.preview_images);
  //           setGalleryPreview(data.preview_images || []);
  //         }
  //       } catch (error) {
  //         console.error("Error fetching gallery preview:", error);
  //       }
  //     }
  //   };
  //   
  //   fetchGalleryPreview();
  // }, [selectedSpecies, API_BASE_URL]);

  const handleModelChange = (event) => {
    const modelType = event.target.value;
    setSelectedModel(modelType);
    setErrorMessage('');
    
    // Reset selections when model changes
    setSelectedSpecies('');
    setQuerySetFile(null);
    setGallerySetFile(null);
    setUseGlobalGallery(false);
  };

  const handleSpeciesChange = (event) => {
    const speciesId = event.target.value;
    setSelectedSpecies(speciesId);
    setErrorMessage('');
    
    // Reset file selections when species changes
    setQuerySetFile(null);
    setGallerySetFile(null);
  };

  const handleGallerySourceChange = (useGlobal) => {
    setUseGlobalGallery(useGlobal);
    if (useGlobal) {
      setGallerySetFile(null);
      setGalleryPreCropped(false);
    }
    setErrorMessage('');
  };

  const validateFile = (file) => {
    if (!file) return true;
    const fileName = file.name.toLowerCase();
    const supportedFormats = ['.zip', '.tar', '.tar.gz', '.tgz'];
    const isSupported = supportedFormats.some(ext => fileName.endsWith(ext)) || 
                       file.type.includes('gzip');
    return isSupported;
  };

  const handleQueryFileChange = (event) => {
    const file = event.target.files[0];
    if (!file) {
      setQuerySetFile(null);
      return;
    }
    
    if (validateFile(file)) {
      setQuerySetFile(file);
      setErrorMessage('');
    } else {
      setQuerySetFile(null);
      setErrorMessage('Query set must be in supported formats: .zip, .tar, .tar.gz, .tgz');
    }
  };

  const handleGalleryFileChange = (event) => {
    const file = event.target.files[0];
    if (!file) {
      setGallerySetFile(null);
      return;
    }
    
    if (validateFile(file)) {
      setGallerySetFile(file);
      setErrorMessage('');
    } else {
      setGallerySetFile(null);
      setErrorMessage('Gallery set must be in supported formats: .zip, .tar, .tar.gz, .tgz');
    }
  };

  const handleUpload = async () => {
    // Validation
    if (!selectedModel) {
      setErrorMessage('Please select a feature extraction model first');
      return;
    }

    if (!selectedSpecies) {
      setErrorMessage('Please select a species first');
      return;
    }

    if (!querySetFile) {
      setErrorMessage('Please upload a query set');
      return;
    }

    if (!useGlobalGallery && !gallerySetFile) {
      setErrorMessage('Please upload a gallery set or use global gallery');
      return;
    }

    if (useGlobalGallery && !globalGalleryStatus.has_global_gallery) {
      setErrorMessage('No global gallery available for this species. Please upload your own gallery set.');
      return;
    }

    setIsUploading(true);
    setErrorMessage('');
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('feature_model', selectedModel);
      formData.append('species_id', selectedSpecies);
      formData.append('use_global_gallery', useGlobalGallery);
      formData.append('query_set', querySetFile);
      formData.append('query_pre_cropped', queryPreCropped);
      formData.append('consent', userConsent);
      formData.append('clear_previous', false);

      if (!useGlobalGallery && gallerySetFile) {
        formData.append('gallery_set', gallerySetFile);
        formData.append('gallery_pre_cropped', galleryPreCropped);
      }

      const xhr = new XMLHttpRequest();
      xhr.withCredentials = true;
      
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(percentComplete);
        }
      });

      xhr.open('POST', `${API_BASE_URL}/reid/upload`);
      
      const response = await new Promise((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText));
            } catch (e) {
              reject(new Error('Invalid JSON response'));
            }
          } else {
            try {
              const errorData = JSON.parse(xhr.responseText);
              reject(new Error(errorData.detail || `HTTP error ${xhr.status}: ${xhr.statusText}`));
            } catch (e) {
              reject(new Error(`HTTP error ${xhr.status}: ${xhr.statusText}`));
            }
          }
        };
        xhr.onerror = () => reject(new Error('Network error'));
        xhr.send(formData);
      });

      navigate('/reid/collage', { state: { sessionId: response.session_id } });
    } catch (error) {
      setErrorMessage(`Upload failed: ${error.message}`);
      console.error('Upload error:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleViewSession = (sessionId) => {
    navigate('/reid/collage', { state: { sessionId } });
  };

  const handleDeleteSession = async (sessionId, event) => {
    event.stopPropagation();
    
    if (!window.confirm("Are you sure you want to delete this session? This action cannot be undone.")) {
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/reid/sessions/${sessionId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        setSessions(sessions.filter(session => session.id !== sessionId));
      } else {
        const error = await response.json();
        alert(`Error deleting session: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error("Error deleting session:", error);
      alert("Failed to delete session. Please try again.");
    }
  };

  const handleDownloadResults = async (sessionId, event) => {
    event.stopPropagation();
    
    try {
      const res = await fetch(`${API_BASE_URL}/reid/download/${sessionId}`, {
        method: 'GET',
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reid_results_${sessionId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading results:", error);
      alert("Failed to download results. Please try again later.");
    }
  };

  const toggleSessions = () => {
    setShowSessions(!showSessions);
  };

  const toggleGalleryManagement = () => {
    setShowGalleryManagement(!showGalleryManagement);
  };

  const getSpeciesName = (speciesId) => {
    const species = speciesList.find(s => s.id === parseInt(speciesId));
    return species ? species.name : 'Unknown Species';
  };

  const getSpeciesId = (speciesName) => {
    // Try exact match first
    let species = speciesList.find(s => s.name === speciesName);
    
    // If no exact match, try case-insensitive match
    if (!species) {
      species = speciesList.find(s => s.name.toLowerCase() === speciesName.toLowerCase());
    }
    
    // If still no match, try partial match
    if (!species) {
      species = speciesList.find(s => 
        s.name.toLowerCase().includes(speciesName.toLowerCase()) ||
        speciesName.toLowerCase().includes(s.name.toLowerCase())
      );
    }
    
    if (!species) {
      console.warn(`Species not found: "${speciesName}". Available species:`, speciesList.map(s => s.name));
    }
    
    return species ? species.id : null;
  };

  const getProcessingStatusDisplay = (status, progress) => {
    switch (status) {
      case 'uploading':
        return 'Uploading...';
      case 'processing':
        return `Processing (${progress}%)`;
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return status;
    }
  };

  const handlePreviewSpecies = async (speciesName) => {
    console.log('Previewing species:', speciesName);
    console.log('Available species list:', speciesList.map(s => ({ id: s.id, name: s.name })));
    
    const speciesId = getSpeciesId(speciesName);
    if (!speciesId) {
      alert(`Species not found: "${speciesName}". Check console for available species.`);
      return;
    }
    
    console.log('Found species ID:', speciesId);

    try {
      const response = await fetch(`${API_BASE_URL}/reid/gallery-sets/${speciesId}/preview`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setPreviewImages(data.images || []);
        setPreviewSpecies(speciesName);
        setShowSpeciesPreview(true);
      } else {
        const error = await response.json();
        alert(`Error loading preview: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error("Error fetching species preview:", error);
      alert("Failed to load preview. Please try again.");
    }
  };

  const handleDownloadSpecies = async (speciesName) => {
    const speciesId = getSpeciesId(speciesName);
    if (!speciesId) {
      alert('Species not found');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/reid/gallery-sets/${speciesId}/download`, {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error ${response.status}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `gallery_${speciesName.replace(' ', '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading species gallery:", error);
      alert(`Failed to download gallery: ${error.message}`);
    }
  };

  return (
    <div className="reid-page-container">
      <Header activeLink="home" showNotification={false}>
        <div className="nav-dropdown">
          <button className="nav-link dropdown-toggle">
            Gallery Management ▼
          </button>
          <div className="dropdown-menu">
            <button onClick={toggleGalleryManagement}>
              My Gallery Sets
            </button>
          </div>
        </div>
      </Header>
      
      <div className="reid-landing-container">
        <div className="reid-landing-content">
          <h1>Wildlife Re-Identification</h1>
          <p>Upload query and gallery image sets to analyze and match wildlife images</p>

          {/* Model Selection */}
          <div className="species-selection">
            <h2>Step 1: Select Feature Extraction Model</h2>
            <select 
              value={selectedModel} 
              onChange={handleModelChange}
              disabled={isUploading}
              className="species-dropdown"
            >
              <option value="megadescriptor">MegaDescriptor (Default)</option>
              <option value="miewid">MiewID</option>
            </select>
            <div style={{ marginTop: '10px', fontSize: '14px', color: '#7f8c8d' }}>
              {selectedModel === 'megadescriptor' && 
                'MegaDescriptor: General-purpose wildlife feature extraction model'}
              {selectedModel === 'miewid' && 
                'MiewID: Specialized model for individual wildlife identification'}
            </div>
          </div>

          {/* Species Selection */}
          <div className="species-selection">
            <h2>Step 2: Select Species</h2>
            <select 
              value={selectedSpecies} 
              onChange={handleSpeciesChange}
              disabled={isUploading}
              className="species-dropdown"
            >
              <option value="">-- Select a species --</option>
              {speciesList.map(species => (
                <option key={species.id} value={species.id}>
                  {species.name}
                </option>
              ))}
            </select>
          </div>

          {selectedSpecies && (
            <>
              {/* Gallery Source Selection */}
              <div className="gallery-source-selection">
                <h2>Step 3: Choose Gallery Source</h2>
                <div className="gallery-options">
                  <div className="gallery-option">
                    <input
                      type="radio"
                      id="global-gallery"
                      name="gallery-source"
                      checked={useGlobalGallery}
                      onChange={() => handleGallerySourceChange(true)}
                      disabled={!globalGalleryStatus.has_global_gallery || isUploading}
                    />
                    <label htmlFor="global-gallery">
                      Use Global Gallery 
                      {globalGalleryStatus.has_global_gallery ? 
                        ` (${globalGalleryStatus.gallery_size} images available)` : 
                        " (Not available for this species)"
                      }
                    </label>
                  </div>
                  <div className="gallery-option">
                    <input
                      type="radio"
                      id="own-gallery"
                      name="gallery-source"
                      checked={!useGlobalGallery}
                      onChange={() => handleGallerySourceChange(false)}
                      disabled={isUploading}
                    />
                    <label htmlFor="own-gallery">Upload My Own Gallery Set</label>
                  </div>
                </div>

                {/* COMMENTED OUT - PRIVACY FIX: Prevents display of non-consented global gallery images */}
                {/* Gallery Preview */}
                {/* {galleryPreview.length > 0 && (
                  <div className="gallery-preview">
                    <h3>Available Gallery Images for {getSpeciesName(selectedSpecies)}</h3>
                    <div className="preview-grid">
                      {galleryPreview.slice(0, 8).map((img, index) => (
                        <div key={index} className="preview-item">
                          <img 
                            src={`${API_BASE_URL}/reid/images/${img.session_id}/${img.image_path}`} 
                            alt={`${img.animal_id}`}
                            className="preview-image"
                            onError={(e) => {
                              console.error('Gallery preview image failed to load:', {
                                url: e.target.src,
                                session_id: img.session_id,
                                image_path: img.image_path,
                                animal_id: img.animal_id
                              });
                              e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgZmlsbD0iI2VlZWVlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTIiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmaWxsPSIjOTk5OTk5Ij5JbWFnZSBOb3QgRm91bmQ8L3RleHQ+PC9zdmc+';
                              e.target.onerror = null;
                            }}
                          />
                          <div className="preview-label">
                            {img.animal_id} {img.is_global && '(Global)'}
                          </div>
                        </div>
                      ))}
                      {galleryPreview.length > 8 && (
                        <div className="preview-more">
                          +{galleryPreview.length - 8} more
                        </div>
                      )}
                    </div>
                  </div>
                )} */}
              </div>

              {/* Upload Section */}
              <div className="upload-section">
                <h2>Step 4: Upload Images</h2>
                
                {/* Query Set Upload */}
                <div className="upload-box">
                  <h3>Query Set</h3>
                  <p>Upload an archive file containing query images</p>
                  <input
                    type="file"
                    id="query-set"
                    accept=".zip,.tar,.tar.gz,.tgz,application/gzip,application/x-gzip"
                    onChange={handleQueryFileChange}
                    disabled={isUploading}
                  />
                  <label htmlFor="query-set" className={querySetFile ? 'file-selected' : ''}>
                    {querySetFile ? querySetFile.name : 'Select Query Set Archive'}
                  </label>
                  
                  <div className="crop-option">
                    <input
                      type="checkbox"
                      id="query-pre-cropped"
                      checked={queryPreCropped}
                      onChange={(e) => setQueryPreCropped(e.target.checked)}
                      disabled={isUploading}
                    />
                    <label htmlFor="query-pre-cropped">
                      Images are already cropped (animals only)
                    </label>
                  </div>
                </div>

                {/* Gallery Set Upload (if not using global) */}
                {!useGlobalGallery && (
                  <div className="upload-box">
                    <h3>Gallery Set</h3>
                    <p>Upload an archive file containing gallery images</p>
                    <input
                      type="file"
                      id="gallery-set"
                      accept=".zip,.tar,.tar.gz,.tgz,application/gzip,application/x-gzip"
                      onChange={handleGalleryFileChange}
                      disabled={isUploading}
                    />
                    <label htmlFor="gallery-set" className={gallerySetFile ? 'file-selected' : ''}>
                      {gallerySetFile ? gallerySetFile.name : 'Select Gallery Set Archive'}
                    </label>
                    
                    <div className="crop-option">
                      <input
                        type="checkbox"
                        id="gallery-pre-cropped"
                        checked={galleryPreCropped}
                        onChange={(e) => setGalleryPreCropped(e.target.checked)}
                        disabled={isUploading}
                      />
                      <label htmlFor="gallery-pre-cropped">
                        Images are already cropped (animals only)
                      </label>
                    </div>
                  </div>
                )}
              </div>

              <div className="upload-options">
                <div className="consent-option">
                  <input
                    type="checkbox"
                    id="consent"
                    checked={userConsent}
                    onChange={(e) => setUserConsent(e.target.checked)}
                    disabled={isUploading}
                  />
                  <label htmlFor="consent">
                    I consent to store these images for future use
                  </label>
                </div>
              </div>

              {errorMessage && <div className="error-message">{errorMessage}</div>}

              {isUploading && (
                <div className="progress-container">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                  <div className="progress-text">{uploadProgress}% Uploaded</div>
                </div>
              )}

              <button
                className="upload-button"
                onClick={handleUpload}
                disabled={!selectedModel || !selectedSpecies || !querySetFile || (!useGlobalGallery && !gallerySetFile) || isUploading}
              >
                {isUploading ? 'Processing...' : 'Start Re-Identification'}
              </button>
            </>
          )}
          
          {/* Previous Sessions */}
          {sessions.length > 0 && (
            <div className="previous-sessions">
              <button 
                className="toggle-sessions-button" 
                onClick={toggleSessions}
              >
                {showSessions ? 'Hide Previous Sessions' : 'Show Previous Sessions'}
              </button>
              
              {showSessions && (
                <div className="sessions-list">
                  <h3>Your Previous Sessions</h3>
                  <div className="sessions-grid">
                    <div className="session-header">
                      <div>Date</div>
                      <div>Species</div>
                      <div>Model</div>
                      <div>Status</div>
                      <div>Images</div>
                      <div>Actions</div>
                    </div>
                    
                    {sessions.map(session => (
                      <div 
                        key={session.id} 
                        className="session-item"
                        onClick={() => session.processing_status === 'completed' && handleViewSession(session.id)}
                        style={{ cursor: session.processing_status === 'completed' ? 'pointer' : 'default' }}
                      >
                        <div>{session.created_at}</div>
                        <div>{session.species_name}</div>
                        <div>{session.feature_model === 'miewid' ? 'MiewID' : 'MegaDescriptor'}</div>
                        <div className={`status-${session.processing_status}`}>
                          {getProcessingStatusDisplay(session.processing_status, session.progress_percentage)}
                        </div>
                        <div>
                          Q:{session.query_count} 
                          {session.use_global_gallery ? ' | Global Gallery' : ` | G:${session.gallery_count}`}
                        </div>
                        <div className="session-actions">
                          <button 
                            className="download-button"
                            onClick={(e) => handleDownloadResults(session.id, e)}
                            disabled={session.processing_status !== 'completed'}
                            title={session.processing_status !== 'completed' ? 'Available when processing is complete' : 'Download results'}
                          >
                            Download
                          </button>
                          <button 
                            className="delete-button"
                            onClick={(e) => handleDeleteSession(session.id, e)}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Gallery Management Modal */}
          {showGalleryManagement && (
            <div className="modal-overlay">
              <div className="gallery-management-modal">
                <div className="modal-header">
                  <h2>Gallery Management</h2>
                  <button 
                    className="close-button"
                    onClick={() => setShowGalleryManagement(false)}
                  >
                    ×
                  </button>
                </div>
                <div className="modal-content">
                  <div className="gallery-management-content">
                    <h3>Your Gallery Collections</h3>
                    <p>Manage your uploaded gallery sets by species:</p>
                    
                    <div className="gallery-stats">
                      <div className="stat-card">
                        <h4>Total Species</h4>
                        <p className="stat-number"> 
                          {/* check */}
                          {[...new Set(sessions.filter(s => !s.use_global_gallery).map(s => s.species_name))].length}
                        </p>
                      </div>
                      <div className="stat-card">
                        <h4>Gallery Images</h4>
                        <p className="stat-number"> 
                          {sessions.filter(s => !s.use_global_gallery).reduce((sum, s) => sum + s.gallery_count, 0)}
                        </p>
                      </div>
                      <div className="stat-card">
                        <h4>Global Contributions</h4>
                        <p className="stat-number">
                          {sessions.filter(s => s.consent && !s.use_global_gallery).length}
                        </p>
                      </div>
                    </div>

                    <div className="species-gallery-list">
                      <h4>Gallery Sets by Species</h4>
                      {[...new Set(sessions.filter(s => !s.use_global_gallery).map(s => s.species_name))].map(speciesName => {
                        const speciesSessions = sessions.filter(s => s.species_name === speciesName && !s.use_global_gallery);
                        const totalImages = speciesSessions.reduce((sum, s) => sum + s.gallery_count, 0);
                        const globalContributions = speciesSessions.filter(s => s.consent).length;
                        
                        return (
                          <div key={speciesName} className="species-gallery-item">
                            <div className="species-info">
                              <h5>{speciesName}</h5>
                              <p>{totalImages} images across {speciesSessions.length} uploads</p>
                              {globalContributions > 0 && (
                                <p className="global-contribution">
                                  {globalContributions} upload(s) contributed to global gallery
                                </p>
                              )}
                            </div>
                            <div className="species-actions">
                              <button 
                                className="preview-button"
                                onClick={() => handlePreviewSpecies(speciesName)}
                              >
                                Preview
                              </button>
                              <button 
                                className="download-species-button"
                                onClick={() => handleDownloadSpecies(speciesName)}
                              >
                                Download All
                              </button>
                            </div>
                          </div>
                        );
                      })}
                      
                      {sessions.filter(s => !s.use_global_gallery).length === 0 && (
                        <div className="no-gallery-sets">
                          <p>No gallery sets uploaded yet.</p>
                          <p>Upload some gallery images to see them here!</p>
                        </div>
                      )}
                    </div>

                    {/* <div className="gallery-tips">
                      <h4>Tips</h4>
                      <ul>
                        <li>Gallery images with consent contribute to the global gallery for all users</li>
                        <li>Pre-cropped images process faster and may give better results</li>
                        <li>Use consistent animal IDs in filenames for better organization</li>
                        <li>Higher quality images generally produce better matching results</li>
                      </ul>
                    </div> */}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Species Preview Modal - Shows user's own gallery sets */}
          {showSpeciesPreview && (
            <div className="modal-overlay">
              <div className="species-preview-modal">
                <div className="modal-header">
                  <h2>Gallery Preview: {previewSpecies}</h2>
                  <button 
                    className="close-button"
                    onClick={() => setShowSpeciesPreview(false)}
                  >
                    ×
                  </button>
                </div>
                <div className="modal-content">
                  <div className="species-preview-content">
                    {previewImages.length > 0 ? (
                      <>
                        <p>Showing {previewImages.length} recent images from your {previewSpecies} gallery:</p>
                        <div className="preview-image-grid">
                          {previewImages.map((image, index) => (
                            <div key={index} className="preview-image-item">
                              <img 
                                src={`${API_BASE_URL}/reid/images/${image.session_id}/${image.image_path}`}
                                alt={`Animal ${image.animal_id}`}
                                className="preview-image"
                                onError={(e) => {
                                  e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgZmlsbD0iI2VlZWVlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTIiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmaWxsPSIjOTk5OTk5Ij5JbWFnZSBOb3QgRm91bmQ8L3RleHQ+PC9zdmc+';
                                  e.target.onerror = null;
                                }}
                              />
                              <div className="preview-image-label">
                                ID: {image.animal_id}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="preview-actions">
                          <button 
                            className="download-species-button"
                            onClick={() => {
                              handleDownloadSpecies(previewSpecies);
                              setShowSpeciesPreview(false);
                            }}
                          >
                            Download All Images
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="no-preview-images">
                        <p>No gallery images found for {previewSpecies}.</p>
                        <p>Upload some gallery images to see them here!</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LandingPage;