import { requestJson } from './http';
import type {
  AccessControlPayload,
  CompanyProfile,
  InitialOfficeSetupResult,
  SetupChatCapability,
  SetupChatRequest,
  SetupChatResponse,
} from './types';

export function analyzeInitialOfficeSetup(payload: {
  message: string;
  upload_ids: string[];
  intent?: string;
  company_profile?: CompanyProfile;
}): Promise<InitialOfficeSetupResult> {
  return requestJson<InitialOfficeSetupResult>('/api/setup/office/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface ApplySetupResponse {
  ok: boolean;
  access_control: AccessControlPayload;
  /** One-time passwords for users created by this apply — shown once, never persisted. */
  issued_credentials: Record<string, string>;
}

export function applyInitialOfficeSetup(payload: InitialOfficeSetupResult): Promise<ApplySetupResponse> {
  return requestJson<ApplySetupResponse>('/api/setup/office/apply', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * One turn of the Solar-driven setup conversation. Falls back to
 * `analyzeInitialOfficeSetup` when the configured model cannot call tools.
 */
export function sendSetupChat(payload: SetupChatRequest): Promise<SetupChatResponse> {
  return requestJson<SetupChatResponse>('/api/setup/office/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchSetupChatCapability(): Promise<SetupChatCapability> {
  return requestJson<SetupChatCapability>('/api/setup/office/chat/capability');
}
