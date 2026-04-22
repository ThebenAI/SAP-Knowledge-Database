const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

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
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
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
