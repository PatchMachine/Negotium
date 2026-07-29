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

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('로그인이 필요합니다.');
    }
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }

  return (await response.json()) as T;
}
