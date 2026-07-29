import { getAuthHeaders } from '../auth';
import { handleAuthFailure, requestJson } from './http';
import type {
  UploadRecord,
} from './types';

export function fetchUploads(): Promise<{ uploads: UploadRecord[] }> {
  return requestJson<{ uploads: UploadRecord[] }>('/api/uploads');
}

export async function uploadDocument(formData: FormData): Promise<{ ok: boolean; upload: UploadRecord }> {
  const response = await fetch('/api/uploads', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('로그인이 필요합니다.');
    }
    throw new Error(await response.text());
  }
  return (await response.json()) as { ok: boolean; upload: UploadRecord };
}

export function deleteUpload(uploadId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/uploads/${uploadId}`, { method: 'DELETE' });
}
