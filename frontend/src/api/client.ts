function normalizeApiBaseUrl(rawValue: string | undefined, fallback: string): string {
  const candidate = (rawValue ?? "").trim();
  if (!candidate) {
    return fallback;
  }
  try {
    const parsed = new URL(candidate);
    // Guard malformed envs like "http://:8000/api" (empty host) or unsupported protocols.
    if (!parsed.hostname || (parsed.protocol !== "http:" && parsed.protocol !== "https:")) {
      return fallback;
    }
    return `${parsed.origin}${parsed.pathname}`.replace(/\/+$/, "");
  } catch {
    return fallback;
  }
}

const API_BASE_URL = import.meta.env.DEV
  ? "http://127.0.0.1:8000/api"
  : (import.meta.env.VITE_API_URL || "https://sap-knowledge-database.onrender.com/api");
  
const AUTH_TOKEN_KEY = "sap_auth_token";

export function getStoredAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setStoredAuthToken(token: string | null): void {
  if (!token) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    return;
  }
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredAuthToken();
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const requestUrl = `${API_BASE_URL}${normalizedPath}`;
  if (import.meta.env.DEV) {
    console.info("[apiFetch]", {
      method: init?.method ?? "GET",
      url: requestUrl,
      hasAuthHeader: headers.has("Authorization"),
      hasBody: Boolean(init?.body),
    });
  }
  const response = await fetch(requestUrl, { ...init, headers });
  if (!response.ok) {
    if (response.status === 401) {
      setStoredAuthToken(null);
      window.dispatchEvent(new Event("auth:required"));
      throw new Error("AUTH_REQUIRED");
    }
    if (response.status === 403) {
      throw new Error("FORBIDDEN");
    }
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export { API_BASE_URL };
