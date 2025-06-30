import React, { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './HomePage.module.css';
import Header from './Common/Header';

const HomePage = () => {
  const navigate = useNavigate();

  const handleRedirect = useCallback(
    (path) => {
      navigate(path);
    },
    [navigate]
  );

  return (
    <>
      <Header />
      <div className={styles.container}>
        <h1 className={styles.title}>Human-in-the-loop Visual Wildlife Monitoring Systems</h1>
        <div className={styles.buttonContainer}>
          <button
            type="button"
            className={styles.button}
            onClick={() => handleRedirect('/species-segregation')}
          >
            Species Segregation
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => handleRedirect('/upload')}
          >
            Bird Count
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => handleRedirect('/re-identification-landing-page')}
          >
            Re-Identification
          </button>
        </div>
      </div>
    </>
  );
};

export default HomePage;