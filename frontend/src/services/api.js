import axios from "axios";
import { API_BASE_URL } from "@/config";

const API = axios.create({
  baseURL: API_BASE_URL,
});

// Request Interceptor: Attach Session ID to headers if it exists
API.interceptors.request.use(
  (config) => {
    const sessionId =
      localStorage.getItem("aeroinbox_session_id") ||
      localStorage.getItem("google_access_token");
    if (sessionId) {
      config.headers.Authorization = `Bearer ${sessionId}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response Interceptor: Capture session expiration and perform refresh
API.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Check if the response is 401 Unauthorized and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const email = localStorage.getItem("user_email");
      const sessionId =
        localStorage.getItem("aeroinbox_session_id") ||
        localStorage.getItem("google_access_token");

      if (email && sessionId) {
        try {
          // Request session refresh from backend using session ID and email
          const response = await axios.post(
            `${API.defaults.baseURL}/auth/refresh`,
            {
              email: email,
              session_id: sessionId,
            },
          );

          const { session_id } = response.data;

          // Store the fresh session ID
          localStorage.setItem("aeroinbox_session_id", session_id);
          localStorage.setItem("google_access_token", session_id);

          // Retry original request with the new session ID
          originalRequest.headers.Authorization = `Bearer ${session_id}`;
          return API(originalRequest);
        } catch (refreshError) {
          console.error(
            "OAuth session refresh failed. Redirecting to login.",
            refreshError,
          );
          localStorage.removeItem("google_access_token");
          localStorage.removeItem("aeroinbox_session_id");
          localStorage.removeItem("google_refresh_token");
          localStorage.removeItem("user_email");
          localStorage.removeItem("aeroinbox_accounts");
          window.location.href = "/";
          return Promise.reject(refreshError);
        }
      } else {
        localStorage.removeItem("google_access_token");
        localStorage.removeItem("aeroinbox_session_id");
        localStorage.removeItem("google_refresh_token");
        localStorage.removeItem("user_email");
        localStorage.removeItem("aeroinbox_accounts");
        window.location.href = "/";
      }
    }

    return Promise.reject(error);
  },
);

export default API;
