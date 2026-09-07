import { apiFetch, extractErrorMessage } from "@/api/client";
import type { ApiUser } from "@/types";

export async function fetchCurrentUser(): Promise<ApiUser> {
  const res = await apiFetch("/auth/me");
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

export async function login(email: string, password: string): Promise<ApiUser> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Registration only -- does not log the new user in (no cookie is set by
// this endpoint). Callers that want the user signed in immediately after
// should call login() with the same credentials right after this resolves.
export async function register(email: string, name: string, password: string): Promise<ApiUser> {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, name, password }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}
