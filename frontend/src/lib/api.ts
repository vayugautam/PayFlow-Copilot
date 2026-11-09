import axios from "axios";

export const TOKEN_KEY = "payflow_access_token";

export const api = axios.create({
  // During local Vite development, use the same-origin proxy so browser CORS
  // enforcement cannot hide a useful API response (such as an expired session).
  baseURL: import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "/api/v1" : "http://127.0.0.1:8000/api/v1"),
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("payflow:unauthorized"));
    }
    return Promise.reject(error);
  },
);

export function getApiError(error: unknown, fallback = "Something went wrong. Please try again.") {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}
