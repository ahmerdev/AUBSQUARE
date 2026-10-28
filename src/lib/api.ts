/**
 * Tiny typed client for the Django REST API.
 *  - Same-origin by default (`/api/v1`, proxied by Vite in dev and served by Django in production).
 *  - Set VITE_API_BASE to point at a separately hosted API.
 *  - Never sends credentials: the public API is anonymous.
 */
const BASE = ((import.meta as any).env?.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || '/api/v1';

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, string | string[]> | null;
  constructor(status: number, message: string, code = 'error', details: ApiError['details'] = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...rest,
      credentials: 'omit',
      headers: { Accept: 'application/json', ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(headers || {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'Network error. Please check your connection and try again.', 'network');
  }
  if (res.status === 204) return undefined as T;
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error page */
  }
  if (!res.ok) {
    const err = body?.error;
    const throttled = res.status === 429;
    throw new ApiError(
      res.status,
      throttled ? 'You are doing that too often. Please wait a few minutes and try again.' : err?.message || body?.detail || `Request failed (${res.status})`,
      err?.code || (throttled ? 'throttled' : 'error'),
      err?.details || null,
    );
  }
  return body as T;
}

/** The `?preview=` token (issued from the dashboard) lets editors see unpublished content. Forwarded to detail endpoints only. */
export function previewQuery(): string {
  if (typeof window === 'undefined') return '';
  const t = new URLSearchParams(window.location.search).get('preview');
  return t ? `?preview=${encodeURIComponent(t)}` : '';
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
  page?: number;
  pages?: number;
}
