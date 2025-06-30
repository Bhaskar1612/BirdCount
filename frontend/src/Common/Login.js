import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser, loginGuest } from "../ObjectDetection/api/authApi";
import loginStyles from "./Login.module.css";
import ReCAPTCHA from "react-google-recaptcha";
import { FaEye, FaEyeSlash } from "react-icons/fa"; // add this

const Login = () => {
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();

  const recaptchaRef = useRef(null);
  const [credentials, setCredentials] = useState({
    username: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [captchaValue, setCaptchaValue] = useState(null);

  const [showGuestCredentials, setShowGuestCredentials] = useState(false);
  const [guestUsername, setGuestUsername] = useState("");
  const [guestPassword, setGuestPassword] = useState("");
  const [copyStatus, setCopyStatus] = useState({
    username: "idle",
    password: "idle",
  });

  const handleChange = (e) =>
    setCredentials({ ...credentials, [e.target.name]: e.target.value });

  const handleCaptchaChange = (value) => {
    setCaptchaValue(value);
    setError("");
  };

  const resetCaptcha = () => {
    if (recaptchaRef.current) {
      recaptchaRef.current.reset();
      setCaptchaValue(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!captchaValue) {
      setError("Please complete the captcha.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await loginUser(credentials.username, credentials.password, captchaValue);
      resetCaptcha();
      navigate("/");
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError("Invalid username or password.");
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
      resetCaptcha();
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text, field) => {
    let success = false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        success = true;
      } catch (err) {
        console.error("Async clipboard write failed:", err);
      }
    }

    if (!success) {
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.top = "-9999px";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        success = document.execCommand("copy");
        document.body.removeChild(textArea);
        if (!success) {
          throw new Error("execCommand failed");
        }
      } catch (err) {
        console.error("Fallback clipboard write failed:", err);
      }
    }

    if (success) {
      setCopyStatus({ ...copyStatus, [field]: "copied" });
      setTimeout(
        () => setCopyStatus((prev) => ({ ...prev, [field]: "idle" })),
        1500
      );
    } else {
      setCopyStatus({ ...copyStatus, [field]: "failed" });
      setTimeout(
        () => setCopyStatus((prev) => ({ ...prev, [field]: "idle" })),
        2000
      );
    }
  };

  const handleGuest = async () => {
    if (!captchaValue) {
      setError("Please complete the captcha.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const guestData = await loginGuest(captchaValue);
      setGuestUsername(guestData.username);
      setGuestPassword(guestData.password);
      setShowGuestCredentials(true);
      resetCaptcha();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Guest login failed. Please try again."
      );
      resetCaptcha();
    } finally {
      setLoading(false);
    }
  };

  const handleCloseGuestCredentials = () => {
    setShowGuestCredentials(false);
    navigate("/");
  };

  return (
    <div className={loginStyles["login-container"]}>
      {showGuestCredentials && (
        <div className={loginStyles["modal-overlay"]}>
          <div className={loginStyles["guest-credentials-display"]}>
            <h2>Guest Account Created</h2>
            <p className={loginStyles["warning-text"]}>
              <strong>
                Important: Save these credentials. You won't see them again.
              </strong>
            </p>
            <div className={loginStyles["credential-item-minimal"]}>
              <label>Username</label>
              <div className={loginStyles["credential-value-wrapper-minimal"]}>
                <span>{guestUsername}</span>
                <button
                  onClick={() => copyToClipboard(guestUsername, "username")}
                  className={`${loginStyles["copy-button-minimal"]} ${
                    copyStatus.username === "copied"
                      ? loginStyles["copy-success"]
                      : ""
                  } ${
                    copyStatus.username === "failed"
                      ? loginStyles["copy-failed"]
                      : ""
                  }`}
                  title="Copy Username"
                  disabled={copyStatus.username === "copied"}
                >
                  {"📋"}
                </button>
              </div>
            </div>
            <div className={loginStyles["credential-item-minimal"]}>
              <label>Password</label>
              <div className={loginStyles["credential-value-wrapper-minimal"]}>
                <span>{guestPassword}</span>
                <button
                  onClick={() => copyToClipboard(guestPassword, "password")}
                  className={`${loginStyles["copy-button-minimal"]} ${
                    copyStatus.password === "copied"
                      ? loginStyles["copy-success"]
                      : ""
                  } ${
                    copyStatus.password === "failed"
                      ? loginStyles["copy-failed"]
                      : ""
                  }`}
                  title="Copy Password"
                  disabled={copyStatus.password === "copied"}
                >
                  {"📋"}
                </button>
              </div>
            </div>
            <button
              onClick={handleCloseGuestCredentials}
              className={loginStyles["continue-button-minimal"]}
            >
              Continue to App
            </button>
          </div>
        </div>
      )}

      <div className={loginStyles["main-content"]}>
        <section className={loginStyles["login-form"]}>
          <h2>Login</h2>
          <form onSubmit={handleSubmit}>
            <input
              type="text"
              name="username"
              value={credentials.username}
              onChange={handleChange}
              placeholder="Username"
              required
              disabled={loading}
            />
            <div className={loginStyles["password-input-container"]}>
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                value={credentials.password}
                onChange={handleChange}
                placeholder="Password"
                required
                disabled={loading}
                className={loginStyles["password-input"]}
              />
              <span
                className={loginStyles["toggle-password"]}
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? <FaEyeSlash /> : <FaEye />}
              </span>
            </div>

            <ReCAPTCHA
              ref={recaptchaRef}
              sitekey={process.env.REACT_APP_CAPTCHA_SITE_KEY}
              onChange={handleCaptchaChange}
            />
            {error && <p className={loginStyles["error-text"]}>{error}</p>}
            <button
              type="submit"
              className={loginStyles["login-button"]}
              disabled={loading || !captchaValue}
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
          <hr />
          <button
            onClick={handleGuest}
            className={loginStyles["guest-button"]}
            disabled={loading || !captchaValue}
          >
            {loading ? "Processing..." : "Login as Guest"}
          </button>
          <p className={loginStyles.AuthRedirect}>
            Don't have an account?{" "}
            <span onClick={() => navigate("/signup")}>Sign Up</span>
          </p>
        </section>
      </div>
    </div>
  );
};

export default Login;
