const TOKEN_KEY = 'negotium-session-token';

export function getSessionToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setSessionToken(token: string) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export const SESSION_EXPIRED_EVENT = 'negotium:session-expired';

/** Drop the stored token and tell the app shell to fall back to the login page. */
export function notifySessionExpired() {
  setSessionToken('');
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export function getAuthHeaders(): Record<string, string> {
  const token = getSessionToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
    'X-NG-User': `Bearer ${token}`,
  };
}
