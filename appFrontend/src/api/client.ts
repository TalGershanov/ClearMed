const API_BASE = "http://localhost:8000";

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const isFormData = options.body instanceof FormData;
  return fetch(`${API_BASE}${path}`, {
    credentials: "include",
    // A FormData body needs the browser to set its own multipart boundary --
    // forcing application/json here would break document uploads.
    ...(isFormData ? {} : { headers: { "Content-Type": "application/json" } }),
    ...options,
  });
}

export async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === "string") return data.detail;
  } catch {
    // no JSON body -- fall through to the generic message below
  }
  return `Request failed (${res.status})`;
}
