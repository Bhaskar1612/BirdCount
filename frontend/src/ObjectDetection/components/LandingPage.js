import React, { useState, useEffect } from "react";
import Header from "../../Common/Header.js";
import UploadSection from "./UploadSection";
import ObjectDetection from "./ObjectDetection";
import styles from "./styles.module.css";
import { logError } from "../utils/error.js";
import { Link } from "react-router-dom";

const LandingPage = () => {
  const [uploadedImageIds, setUploadedImageIds] = useState([]);
  const [showNotification, setShowNotification] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowNotification(true);
    }, 2000);

    return () => clearTimeout(timer);
  }, []);

  const handleUploadSuccess = (imageIds = []) => {
    if (!Array.isArray(imageIds)) {
      logError("handleUploadSuccess received non-array imageIds:", imageIds);
      imageIds = [];
    }
    setUploadedImageIds((prevIds) => {
      const newIds = [...new Set([...prevIds, ...imageIds])];
      return newIds;
    });
  };

  return (
    <div className={styles["landing-page"]}>
      <Header activeLink="home" showNotification={false}>
        <Link
          to="/active-learning"
          className={`${styles["nav-link"]} ${styles["active-learning-link"]}`}
        >
          Active Learning
          {showNotification && (
            <span className={styles["notification-dot"]}></span>
          )}
        </Link>
      </Header>
      <main className={styles["main-content"]}>
        <section className={styles["hero"]}>
          <h1>AI Wildlife</h1>
          <p>AI tool for species segregation</p>
          <UploadSection onUploadSuccess={handleUploadSuccess} />
        </section>
        <ObjectDetection uploadedImageIds={uploadedImageIds} />
      </main>
    </div>
  );
};

export default LandingPage;
