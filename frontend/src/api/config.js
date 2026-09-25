const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();

export const API_BASE_URL = (configuredApiUrl || (import.meta.env.DEV ? "http://localhost:8000/api/v1" : ""))
  .replace(/\/+$/, "");

export function requireApiBaseUrl() {
  if (!API_BASE_URL) {
    throw new Error("Set VITE_API_URL to the deployed public API base URL ending in /api/v1.");
  }

  if (import.meta.env.PROD && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(?:\/|$)/i.test(API_BASE_URL)) {
    throw new Error("VITE_API_URL points to localhost in a production build. Set it to the deployed public API URL.");
  }

  return API_BASE_URL;
}
