const STORAGE_KEY = 'patch-machine-user-id';
const SAFE_USER_ID = /^[A-Za-z0-9._-]+$/;

function normalizeUserId(userId: string | null): string {
  const trimmed = (userId || '').trim();
  if (!trimmed || !SAFE_USER_ID.test(trimmed)) {
    return 'owner';
  }
  return trimmed;
}

export function getCurrentUserId(): string {
  return normalizeUserId(localStorage.getItem(STORAGE_KEY));
}

export function setCurrentUserId(userId: string) {
  localStorage.setItem(STORAGE_KEY, normalizeUserId(userId));
}
