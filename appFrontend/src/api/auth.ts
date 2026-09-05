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

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}
