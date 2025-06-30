import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './Collage.css';
import Header from "../../Common/Header.js";

const Collage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [matchResults, setMatchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processing, setProcessing] = useState(true);
  const [processingStatus, setProcessingStatus] = useState('uploading');
  const [progressPercentage, setProgressPercentage] = useState(0);
  const [pollingCount, setPollingCount] = useState(0);
  
  const sessionId = location.state?.sessionId;
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL; 
  
  const [showDialog, setShowDialog] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [dialogFeedbackSubmitted, setDialogFeedbackSubmitted] = useState(false);
  
  const [feedbackHistory, setFeedbackHistory] = useState({});
  const [isChangingFeedback, setIsChangingFeedback] = useState(false);

  useEffect(() => {
    // Redirect if no session ID
    if (!sessionId) {
      navigate('/re-identification-landing-page');
      return;
    }
  }, [sessionId, navigate]);

  const fetchResults = useCallback(async () => {
    try {
      console.log(`Fetching results for session: ${sessionId} (attempt ${pollingCount + 1})`);
      const response = await fetch(`${API_BASE_URL}/reid/results/${sessionId}`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch results: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log("Fetched results:", data);
      
      // Update processing status and progress
      setProcessingStatus(data.processing_status);
      setProgressPercentage(data.progress_percentage || 0);
      
      // Check if processing is complete
      if (data.processing_status === 'completed') {
        console.log("Processing complete, rendering results");
        setMatchResults(data.results || []);
        setProcessing(false);
        
        // Fetch feedback data once processing is complete
        try {
          const feedbackResponse = await fetch(`${API_BASE_URL}/reid/feedback?session_id=${sessionId}`, {
            credentials: 'include'
          });
          if (feedbackResponse.ok) {
            const feedbackData = await feedbackResponse.json();
            
            const feedbackMap = {};
            feedbackData.forEach(item => {
              const key = `${item.query_image_id}:${item.gallery_image_id}`;
              feedbackMap[key] = {
                id: item.id,
                isCorrect: item.is_correct
              };
            });
            
            setFeedbackHistory(feedbackMap);
          }
        } catch (err) {
          console.warn("Could not fetch feedback history:", err);
        }
      } else if (data.processing_status === 'failed') {
        setProcessing(false);
        setError("Processing failed. Please try again or contact support.");
      } else {
        // Still processing - continue polling
        console.log(`Status: ${data.processing_status}, Progress: ${data.progress_percentage}%`);
        
        // Store partial results if available
        if (data.results && data.results.length > 0) {
          setMatchResults(data.results);
        }
        
        // Continue polling if we haven't reached the limit
        if (pollingCount < 15000) { // Limit to 150 attempts (25 minutes with 10s interval)
          setPollingCount(prev => prev + 1);
        } else {
          // Stop polling after limit reached
          setProcessing(false);
          setError("Processing is taking longer than expected. Please check back later or contact support.");
        }
      }
    } catch (error) {
      console.error("Error fetching results:", error);
      setError(`Error: ${error.message}`);
      setProcessing(false);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, API_BASE_URL, pollingCount]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    // Initial fetch
    fetchResults();
    
    // Set up polling if still processing
    let pollingInterval;
    if (processing && processingStatus !== 'completed' && processingStatus !== 'failed') {
      pollingInterval = setInterval(() => {
        fetchResults();
      }, 10000); // Poll every 10 seconds
    }

    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [sessionId, fetchResults, processing, processingStatus]);

  const handleBackToUpload = () => {
    navigate('/re-identification-landing-page');
  };

  const handleDownloadResults = async () => {
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
      alert("Failed to download results. Please try again.");
    }
  };

  const handleQuickFeedback = async (queryImageId, galleryImageId, isCorrect) => {
    try {
      // const response = await fetch(`${API_BASE_URL}/reid/feedback`, {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //   },
      //   credentials: 'include',
      //   body: JSON.stringify({
      //     session_id: sessionId,
      //     query_image_id: queryImageId,
      //     gallery_image_id: galleryImageId,
      //     is_correct: isCorrect
      //   }),
      // });

      // In handleQuickFeedback function
      const response = await fetch(`${API_BASE_URL}/reid/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          session_id: sessionId,
          query_image_id: queryImageId,
          gallery_image_id: galleryImageId,
          is_correct: isCorrect
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }
      
      const data = await response.json();
      const feedbackKey = `${queryImageId}:${galleryImageId}`;
      
      // Update feedback history state
      setFeedbackHistory(prev => ({
        ...prev,
        [feedbackKey]: {
          id: data.id,
          isCorrect: isCorrect
        }
      }));
      
      console.log(`Feedback submitted: ${isCorrect ? 'Correct' : 'Incorrect'} match`);
    } catch (error) {
      console.error("Error submitting quick feedback:", error);
      alert(`Error submitting feedback: ${error.message}`);
    }
  };

  const getImageUrl = (imagePath, imageSessionId = null) => {
    if (!imagePath) {
      console.warn("Invalid image path:", imagePath);
      return null;
    }
    
    if (imagePath.includes('__MACOSX') || imagePath.includes('._') || imagePath.includes('.DS_Store')) {
      console.warn("Skipping macOS metadata file:", imagePath);
      return null;
    }
    
    if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
      return imagePath;
    }
    
    // Make sure we're using encodeURIComponent for the path
    const encodedPath = encodeURIComponent(imagePath);
    
    // Use the dedicated image endpoint with appropriate session ID
    const actualSessionId = imageSessionId || sessionId;
    const url = `${API_BASE_URL}/reid/images/${actualSessionId}/${encodedPath}`;
    console.log("Trying to access image URL:", url);
    
    return url;
  };

  const handleImageError = (e) => {
    console.error('Image failed to load:', e.target.src);
    e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZWVlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMjAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmaWxsPSIjOTk5OTk5Ij5JbWFnZSBOb3QgRm91bmQ8L3RleHQ+PC9zdmc+';
    e.target.onerror = null; 
  };

  const getFeedbackForPair = (queryImageId, galleryImageId) => {
    const key = `${queryImageId}:${galleryImageId}`;
    return feedbackHistory[key];
  };

  const handleGalleryImageClick = (queryResult, match) => {
    console.log("Gallery image clicked:", match);
    
    setSelectedMatch({
      queryResult: queryResult,
      match: match
    });
    
    // Check if feedback already exists for this pair
    const existingFeedback = getFeedbackForPair(queryResult.query_image_id, match.gallery_image_id);
    setDialogFeedbackSubmitted(!!existingFeedback);
    setIsChangingFeedback(false);
    
    setShowDialog(true);
  };

  const handleFeedback = async (isCorrect) => {
    try {
      if (!selectedMatch || !selectedMatch.queryResult || !selectedMatch.match) {
        throw new Error('Missing required match information');
      }
      
      const response = await fetch(`${API_BASE_URL}/reid/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          session_id: sessionId,
          query_image_id: selectedMatch.queryResult.query_image_id,
          gallery_image_id: selectedMatch.match.gallery_image_id,
          is_correct: isCorrect
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }
      
      const data = await response.json();
      const feedbackKey = `${selectedMatch.queryResult.query_image_id}:${selectedMatch.match.gallery_image_id}`;
      
      // Update feedback history state
      setFeedbackHistory(prev => ({
        ...prev,
        [feedbackKey]: {
          id: data.id,
          isCorrect: isCorrect
        }
      }));
      
      setDialogFeedbackSubmitted(true);
      setIsChangingFeedback(false);
    } catch (error) {
      console.error("Error submitting feedback:", error);
      alert(`Error submitting feedback: ${error.message}`);
    }
  };

  const getProcessingMessage = () => {
    switch (processingStatus) {
      case 'uploading':
        return 'Uploading and extracting images...';
      case 'processing':
        return 'Processing images and extracting features...';
      default:
        return 'Processing images...';
    }
  };

  if (isLoading && pollingCount === 0) {
    return (
      <div className="collage-container">
        <Header activeLink="home" showNotification={false} />
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>Loading session...</p>
        </div>
      </div>
    );
  }

  if (processing) {
    return (
      <div className="collage-container">
        <Header activeLink="home" showNotification={false} />
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>{getProcessingMessage()}</p>
          <div className="progress-container">
            <div className="progress-bar">
              <div 
                className="progress-fill"
                style={{ width: `${progressPercentage}%` }}
              ></div>
            </div>
            <div className="progress-text">{progressPercentage}% Complete</div>
          </div>
          <p className="processing-details">
            {matchResults.length > 0 ? 
              `Partial results available. Processing ${processingStatus}...` :
              'This may take several minutes depending on the number of images.'}
          </p>
          <button className="back-button" onClick={handleBackToUpload}>
            Back to Upload
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="collage-container">
        <Header activeLink="home" showNotification={false} />
        <div className="error-display">
          <h2>Something went wrong</h2>
          <p>{error}</p>
          <button onClick={handleBackToUpload}>Back to Upload</button>
        </div>
      </div>
    );
  }

  return (
    <div className="collage-container">
      <Header activeLink="home" showNotification={false} />
      <div className="collage-header">
        <h1>Re-Identification Results</h1>
        <div className="action-buttons">
          <button 
            className="download-results-button" 
            onClick={handleDownloadResults}
          >
            Download Results
          </button>
          <button className="back-button" onClick={handleBackToUpload}>
            Back to Upload
          </button>
        </div>
      </div>
      
      {matchResults.length === 0 ? (
        <div className="no-results">
          <p>No matching results found. Please try uploading different image sets.</p>
        </div>
      ) : (
        <div className="collage-content">
          {matchResults.map((resultRow, rowIndex) => (
            <div key={`row-${rowIndex}`} className="result-row">
              <div className="query-image-container">
                {getImageUrl(resultRow.query_image) && (
                  <div className="image-with-original">
                    <img 
                      src={getImageUrl(resultRow.query_image)} 
                      alt={`Query ${rowIndex + 1}`} 
                      className="query-image cropped-image"
                      onError={handleImageError}
                      onClick={() => {
                        // Show original image in modal
                        if (resultRow.original_image_path) {
                          setSelectedMatch({
                            queryResult: resultRow,
                            match: null,
                            showOriginal: true
                          });
                          setShowDialog(true);
                        }
                      }}
                      style={{ cursor: resultRow.original_image_path ? 'pointer' : 'default' }}
                    />
                    <div className="image-label">
                      Query Image (Cropped)
                      {resultRow.original_image_path && <span className="click-hint">Click to see original</span>}
                    </div>
                  </div>
                )}
              </div>

              <div className="gallery-matches">
                {(resultRow.matches || [])
                  .filter(match => getImageUrl(match.image_path)) 
                  .map((match, matchIndex) => {
                    const feedback = getFeedbackForPair(resultRow.query_image_id, match.gallery_image_id);
                    
                    return (
                      <div key={`match-${rowIndex}-${matchIndex}`} className="gallery-image-container">
                        {/* Quick feedback buttons - moved to corners */}
                        <div 
                          className={`quick-feedback-btn-corner correct ${feedback && feedback.isCorrect ? 'selected' : ''}`}
                          title={feedback && feedback.isCorrect ? "Already marked as correct" : "Mark as correct match"}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleQuickFeedback(resultRow.query_image_id, match.gallery_image_id, true);
                          }}
                        >
                          ✓
                        </div>
                        <div 
                          className={`quick-feedback-btn-corner incorrect ${feedback && !feedback.isCorrect ? 'selected' : ''}`}
                          title={feedback && !feedback.isCorrect ? "Already marked as incorrect" : "Mark as incorrect match"}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleQuickFeedback(resultRow.query_image_id, match.gallery_image_id, false);
                          }}
                        >
                          ✗
                        </div>
                        
                        <img 
                          src={getImageUrl(match.image_path, match.session_id)} 
                          alt={`Match ${matchIndex + 1}`} 
                          className={`gallery-image cropped-image ${feedback ? (feedback.isCorrect ? 'correct-match' : 'incorrect-match') : ''}`}
                          onError={handleImageError}
                          onClick={() => handleGalleryImageClick(resultRow, match)}
                        />
                        
                        <div className="match-info">
                          <div className="match-score">Score: {match.score.toFixed(2)}</div>
                          <div className="match-id">ID: {match.id || 'Unknown'}</div>
                          {feedback && (
                            <div className={`match-feedback ${feedback.isCorrect ? 'correct' : 'incorrect'}`}>
                              {feedback.isCorrect ? '✓ Correct' : '✗ Incorrect'}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  
                {/* Show message when no matches are found */}
                {(!resultRow.matches || resultRow.matches.length === 0) && (
                  <div className="no-animals-detected">
                    {/* <div className="no-detection-icon">🔍</div> */}
                    <div className="no-detection-message">
                      <h3>No animals detected</h3>
                      <p>MegaDetector did not find any animals in this query image.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showDialog && selectedMatch && (
        <div className="match-dialog-overlay">
          <div className="match-dialog">
            <div className="match-dialog-header">
              <h2>{selectedMatch.showOriginal ? 'Original Query Image' : 'Compare Images'}</h2>
              <button className="close-button" onClick={() => setShowDialog(false)}>×</button>
            </div>
            <div className="match-dialog-content">
              {selectedMatch.showOriginal ? (
                <div className="original-image-display">
                  <img 
                    src={getImageUrl(selectedMatch.queryResult.original_image_path)} 
                    alt="Original Query" 
                    onError={handleImageError}
                    className="original-display-image"
                  />
                  <p>Original uploaded image before cropping</p>
                </div>
              ) : (
                <>
                  <div className="match-comparison">
                    <div className="comparison-image">
                      <img 
                        src={getImageUrl(selectedMatch.queryResult.query_image)} 
                        alt="Query" 
                        onError={handleImageError}
                      />
                      <div>Query Image (Cropped)</div>
                    </div>
                    <div className="comparison-image">
                      <img 
                        src={getImageUrl(selectedMatch.match.image_path, selectedMatch.match.session_id)} 
                        alt="Match" 
                        onError={handleImageError}
                      />
                      <div>Match Image (ID: {selectedMatch.match.id})</div>
                    </div>
                  </div>
                  <div className="match-details">
                    <p>Confidence score: <strong>{selectedMatch.match.score.toFixed(2)}</strong></p>
                    
                    {dialogFeedbackSubmitted && !isChangingFeedback ? (
                      <div className="feedback-submitted">
                        <p>Your feedback: 
                          <strong>
                            {(() => {
                              const currentFeedback = getFeedbackForPair(
                                selectedMatch.queryResult.query_image_id, 
                                selectedMatch.match.gallery_image_id
                              );
                              return currentFeedback ? 
                                (currentFeedback.isCorrect ? 'This is a correct match' : 'This is an incorrect match') :
                                'No feedback given';
                            })()}
                          </strong>
                        </p>
                        <button 
                          className="change-feedback-button" 
                          onClick={() => setIsChangingFeedback(true)}
                        >
                          Change My Feedback
                        </button>
                      </div>
                    ) : (
                      <div className="feedback-section">
                        <p>Is this match correct?</p>
                        <div className="feedback-buttons">
                          <button 
                            className="feedback-button correct" 
                            onClick={() => handleFeedback(true)}
                          >
                            Yes
                          </button>
                          <button 
                            className="feedback-button incorrect" 
                            onClick={() => handleFeedback(false)}
                          >
                            No
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Collage;