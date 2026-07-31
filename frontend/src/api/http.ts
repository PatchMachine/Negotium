// Shared JSON request helper for the API client modules.
import { getAuthHeaders, notifySessionExpired } from '../auth';

/**
 * Session-expiry hook for responses fetched outside requestJson (uploads,
 * SSE streams). Returns true when the response was a 401 and the app has
 * been told to fall back to the login page.
 */
export function handleAuthFailure(response: Response): boolean {
  if (response.status !== 401) {
    return false;
  }
  notifySessionExpired();
  return true;
}

/**
 * Ceiling on any single API call. Agent-loop turns are bounded server-side at
 * MAX_TURN_SECONDS (300s); this sits above that so a slow-but-alive request is
 * never cut off, while a backend that dies mid-request still rejects instead of
 * leaving the caller's spinner up forever.
 */
const REQUEST_TIMEOUT_MS = 330_000;

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('요청이 응답 제한 시간을 초과했습니다. 다시 시도해 주세요.');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('로그인이 필요합니다.');
    }
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }

  return (await response.json()) as T;
}
