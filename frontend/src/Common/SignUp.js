import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import ReCAPTCHA from "react-google-recaptcha";
import styles from "./SignUp.module.css";

const Signup = () => {
  const navigate = useNavigate();
  const recaptchaRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [captchaValue, setCaptchaValue] = useState(null);
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");

  const usernameRegex = /^[A-Za-z0-9_]{3,20}$/;
  const passwordMin = 8;
  const passwordMax = 20;

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const onCaptchaChange = (value) => {
    setCaptchaValue(value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!usernameRegex.test(form.username)) {
      setError(
        "Username must be 3-20 characters and contain only letters, numbers, and underscores."
      );
      return;
    }

    if (
      form.password.length < passwordMin ||
      form.password.length > passwordMax
    ) {
      setError(
        `Password must be between ${passwordMin} and ${passwordMax} characters.`
      );
      return;
    }

    if (!captchaValue) {
      setError("Please complete the reCAPTCHA.");
      return;
    }

    setLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("username", form.username);
    if (form.email) {
      formData.append("email", form.email);
    }
    formData.append("password", form.password);
    formData.append("captcha_value", captchaValue);

    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE_URL}/auth/signup`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
        }
      );
      if (!response.ok) {
        const errorData = await response.json();
        setError(errorData.detail || "Signup failed");
        return;
      }
      alert("Signup successful! Redirecting to login page.");
      navigate("/login");
    } catch (err) {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.SignupContainer}>
      <div className={styles.SignupForm}>
        <h2>Sign Up</h2>
        <form onSubmit={handleSubmit}>
          <label htmlFor="username">
            Username <span className={styles.Required}>*</span>
          </label>
          <input
            type="text"
            id="username"
            name="username"
            placeholder="Username"
            value={form.username}
            onChange={handleChange}
            required
            disabled={loading}
          />
          <p className={styles.HintText}>
            Username must be 3-20 characters long and can include letters,
            numbers, and underscores.
          </p>

          <label htmlFor="email">
            Email <span className={styles.Optional}>(optional)</span>
          </label>
          <input
            type="email"
            id="email"
            name="email"
            placeholder="Email"
            value={form.email}
            onChange={handleChange}
            disabled={loading}
          />
          <p>
            Provided email may be used later for password resets and other
            features.
          </p>

          <label htmlFor="password">
            Password <span className={styles.Required}>*</span>
          </label>
          <input
            type="password"
            id="password"
            name="password"
            placeholder="Password"
            value={form.password}
            onChange={handleChange}
            required
            disabled={loading}
          />
          <p className={styles.HintText}>
            Password must be between {passwordMin} and {passwordMax} characters.
          </p>

          <div className={styles.recaptchaContainer}>
            <ReCAPTCHA
              ref={recaptchaRef}
              sitekey={process.env.REACT_APP_CAPTCHA_SITE_KEY}
              onChange={onCaptchaChange}
            />
          </div>
          {error && <p className={styles.ErrorText}>{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? "Signing up..." : "Sign Up"}
          </button>
        </form>
        <p className={styles.LoginRedirect}>
          Already have an account?{" "}
          <span onClick={() => navigate("/login")}>Login</span>
        </p>
      </div>
    </div>
  );
};

export default Signup;
