const TOKEN_KEY = 'patch-machine-session-token';

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

export function getAuthHeaders(): Record<string, string> {
  const token = getSessionToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
    'X-PM-User': `Bearer ${token}`,
  };
}
