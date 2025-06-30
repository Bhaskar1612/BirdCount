import React, { useState, useEffect, useRef } from "react";
import styles from "../ObjectDetection/components/styles.module.css";
import { Link, useNavigate } from "react-router-dom";
import axios from "../ObjectDetection/api/api";
import { FaUserCircle } from "react-icons/fa";

const logoPath = "/assets/static/aiwild.webp";
const iiitdLogoPath = "/assets/static/iiitd_logo.webp";
const wiiLogoPath = "/assets/static/wii_logo.webp";
const ntcaLogoPath = "/assets/static/ntca_logo.webp";

const Header = ({ activeLink, showNotification, children }) => {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    axios
      .get("/auth/me")
      .then((res) => setIsAdmin(res.data.is_admin))
      .catch(() => setIsAdmin(false));
  }, []);

  const handleLogout = async () => {
    setMenuOpen(false);
    try {
      await axios.delete("/cleanup");
      await axios.post("/auth/logout");
      sessionStorage.removeItem("isGuest");
      navigate("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  useEffect(() => {
    const onClick = (e) =>
      menuRef.current?.contains(e.target) || setMenuOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <header className={styles["App-header"]}>
      <div className={styles["top-bar"]}>
        <img src={logoPath} alt="AIWilD Logo" className={styles["logo"]} />

        <nav className={styles["nav-links"]}>
          <Link
            to="/"
            className={styles["nav-link"]}
            data-active={activeLink === "home"}
          >
            Home
          </Link>
          {children}
          <a href="#" className={styles["nav-link"]}>
            Team
          </a>
          <a
            href="mailto:ameya21447@iiitd.ac.in"
            className={styles["nav-link"]}
          >
            Contact Us
          </a>

          <div className={styles["profile-menu"]} ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className={styles["nav-link"]}
            >
              <FaUserCircle size={24} />
            </button>
            {menuOpen && (
              <ul className={styles["menu-list"]}>
                {isAdmin && (
                  <li>
                    <Link to="/admin" onClick={() => setMenuOpen(false)}>
                      Admin Dashboard
                    </Link>
                  </li>
                )}
                <li>
                  <button onClick={handleLogout}>Logout</button>
                </li>
              </ul>
            )}
          </div>
        </nav>

        <div className={styles["logo-group"]}>
          <img
            src={ntcaLogoPath}
            alt="NTCA Logo"
            className={styles["small-logo"]}
          />
          <a
            href="https://wii.gov.in"
            target="_blank"
            rel="noopener noreferrer"
          >
            <img
              src={wiiLogoPath}
              alt="WII Logo"
              className={styles["small-logo"]}
            />
          </a>
          <a
            href="https://iiitd.ac.in"
            target="_blank"
            rel="noopener noreferrer"
          >
            <img
              src={iiitdLogoPath}
              alt="IIITD Logo"
              className={styles["small-logo"]}
            />
          </a>
        </div>
      </div>
    </header>
  );
};

export default Header;
