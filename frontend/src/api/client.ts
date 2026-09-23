/**
 * Centralized fetch-based API client.
 *
 * All requests:
 *  - Use credentials: "include" so the browser sends the session_token cookie.
 *  - Set Content-Type: application/json for JSON bodies.
 *  - Throw ApiClientError on non-2xx responses with the detail message from the backend.
 *  - Never expose tokens, passwords, or sensitive data in error messages beyond
 *    what the backend itself returns.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export class ApiClientError extends Error {
  readonly status: number;
  constructor(
    status: number,
    message: string,
  ) {
    super(message);
    this.status = status;
    this.name = 'ApiClientError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    // Some endpoints return an empty body on success
    const text = await res.text();
    return (text ? JSON.parse(text) : {}) as T;
  }

  let detail = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (body?.detail) {
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    }
  } catch {
    // ignore parse errors
  }

  throw new ApiClientError(res.status, detail);
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'GET',
    credentials: 'include',
    headers: { 'Accept': 'application/json' },
  });
  return handleResponse<T>(res);
}

export async function apiPost<TBody, TResponse>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return handleResponse<TResponse>(res);
}

export async function apiPostForm<TResponse>(
  path: string,
  formData: FormData,
): Promise<TResponse> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    // Do NOT set Content-Type — browser sets it with the multipart boundary
    headers: { 'Accept': 'application/json' },
    body: formData,
  });
  return handleResponse<TResponse>(res);
}

export async function apiDelete<TResponse>(path: string): Promise<TResponse> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: { 'Accept': 'application/json' },
  });
  return handleResponse<TResponse>(res);
}

export async function apiPatch<TBody, TResponse>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return handleResponse<TResponse>(res);
}
