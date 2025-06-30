import axiosInstance from "./api";

export const logout = async () => {
  return await axiosInstance.post("/auth/logout");
};

export const loginUser = async (username, password, captchaValue) => {
  const params = new URLSearchParams();
  params.append("username", username);
  params.append("password", password);
  params.append("captcha_value", captchaValue);
  return await axiosInstance.post("/auth/token", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
};

export const loginGuest = async (captchaValue) => {
  const params = new URLSearchParams();
  params.append("captcha_value", captchaValue);
  const response = await axiosInstance.post("/auth/guest", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return response.data;
};
