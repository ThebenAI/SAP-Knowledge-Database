import { apiFetch } from "./client";
import type { AuthLoginRequest, AuthLoginResponse, User, UserCreateRequest, UserUpdateRequest } from "../types/api";

export function login(payload: AuthLoginRequest): Promise<AuthLoginResponse> {
  return apiFetch<AuthLoginResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/users");
}

export function createUser(payload: UserCreateRequest): Promise<User> {
  return apiFetch<User>("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateUser(userId: number, payload: UserUpdateRequest): Promise<User> {
  return apiFetch<User>(`/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function resetUserPassword(userId: number, newPassword: string): Promise<User> {
  return apiFetch<User>(`/users/${userId}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: newPassword }),
  });
}
