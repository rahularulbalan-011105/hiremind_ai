export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type ApiResult = {
  ok: boolean;
  status: number;
  durationMs: number;
  body: unknown;
};

export async function callJson(
  path: string,
  method: "GET" | "POST" | "PUT" | "DELETE",
  body?: unknown
): Promise<ApiResult> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const started = performance.now();
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const duration = performance.now() - started;
  const text = await res.text();
  let parsed: unknown = text;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    /* keep raw text */
  }
  return { ok: res.ok, status: res.status, durationMs: duration, body: parsed };
}

export async function callMultipart(
  path: string,
  form: FormData
): Promise<ApiResult> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const started = performance.now();
  const res = await fetch(url, { method: "POST", body: form });
  const duration = performance.now() - started;
  const text = await res.text();
  let parsed: unknown = text;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    /* keep raw text */
  }
  return { ok: res.ok, status: res.status, durationMs: duration, body: parsed };
}
