import { getCurrentUserId } from './auth';

export type OperationsMemory = {
  company_name: string;
  office_project: string;
  active_plan: string;
  organization: string;
  departments: string;
  roles: string;
  key_workflows: string;
  office_tools: string;
  sensitive_policy: string;
};

export type ApiStatus = {
  ok: boolean;
  queue_size: number;
  queue_capacity: number;
  metrics: Record<string, unknown>;
  operations_memory_configured: boolean;
};

export type LlmProviderName = 'vllm' | 'openai' | 'anthropic' | 'gemini' | 'fake';
export type LlmRuntimeRoute = 'local' | 'api';

export type LlmRuntime = {
  local_enabled: boolean;
  api_enabled: boolean;
  default_route: LlmRuntimeRoute;
  default_provider: LlmProviderName;
  local_model: string;
  vllm_base_url: string;
  openai_model: string;
  anthropic_model: string;
  gemini_model: string;
};

export type ChatResponse = {
  answer: string;
  route: LlmRuntimeRoute;
  provider: LlmProviderName;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
};

export type LocalLlmStatus = {
  enabled: boolean;
  mode: string;
  state: 'disabled' | 'offline' | 'loading' | 'running' | 'error' | 'unavailable' | string;
  model: string;
  loaded: boolean;
  message: string;
  error: string;
  started_at: string;
  ready_at: string;
};

export type ProgressLog = {
  path: string;
  title: string;
  repo: string;
  source: string;
  external_id: string;
  status: string;
  created: string;
  llm_route: string;
  kind?: string;
  summary?: string;
};

export type ProgressPayload = {
  current_status_md: string;
  queue_size: number;
  queue_capacity: number;
  recent_logs: ProgressLog[];
};

export type WorkItemsPayload = {
  items: ProgressLog[];
  bottleneck_summary: string;
};

export type IntegrationStatus = {
  ok: boolean;
  configured: boolean;
  reason: string;
  items: Array<Record<string, unknown>>;
};

export type HiringRequest = {
  role_title: string;
  business_need: string;
  priority: string;
};

export type GeneratedDocument = {
  title: string;
  markdown: string;
  path: string;
};

export type HandoverRequest = {
  work_title: string;
  outgoing_owner: string;
  incoming_owner: string;
  notes: string;
};

export type OfficeDocumentRequest = {
  document_type: 'meeting_minutes' | 'report_draft' | 'work_request' | 'ppt_outline';
  title: string;
  source_text: string;
  audience: string;
};

export type ApiKeyInfo = {
  provider: string;
  configured: boolean;
  masked_value: string;
  model: string;
  base_url: string;
};

export type RoleRecord = {
  id: string;
  name: string;
  level: number;
  permissions: string[];
};

export type UserRecord = {
  id: string;
  display_name: string;
  title: string;
  role_id: string;
  active: boolean;
};

export type AccessControlPayload = {
  roles: RoleRecord[];
  users: UserRecord[];
  permissions: string[];
};

export type UploadRecord = {
  id: string;
  filename: string;
  path: string;
  description: string;
  tags: string;
  work_title: string;
  uploaded_at: string;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      'X-PM-User': getCurrentUserId(),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }

  return (await response.json()) as T;
}

export function fetchOperationsMemory(): Promise<OperationsMemory> {
  return requestJson<OperationsMemory>('/api/operations-memory');
}

export function saveOperationsMemory(memory: OperationsMemory): Promise<OperationsMemory> {
  return requestJson<OperationsMemory>('/api/operations-memory', {
    method: 'PUT',
    body: JSON.stringify(memory),
  });
}

export function fetchApiStatus(): Promise<ApiStatus> {
  return requestJson<ApiStatus>('/api/status');
}

export function fetchLlmRuntime(): Promise<LlmRuntime> {
  return requestJson<LlmRuntime>('/api/llm/runtime');
}

export function saveLlmRuntime(runtime: LlmRuntime): Promise<LlmRuntime> {
  return requestJson<LlmRuntime>('/api/llm/runtime', {
    method: 'PUT',
    body: JSON.stringify(runtime),
  });
}

export function fetchLocalLlmStatus(): Promise<LocalLlmStatus> {
  return requestJson<LocalLlmStatus>('/api/llm/local-status');
}

export function startLocalLlm(): Promise<LocalLlmStatus> {
  return requestJson<LocalLlmStatus>('/api/llm/local/start', { method: 'POST' });
}

export function stopLocalLlm(): Promise<LocalLlmStatus> {
  return requestJson<LocalLlmStatus>('/api/llm/local/stop', { method: 'POST' });
}

export function sendChatMessage(
  message: string,
  route: LlmRuntimeRoute,
  provider: LlmProviderName,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>('/api/llm/chat', {
    method: 'POST',
    body: JSON.stringify({ message, route, provider }),
  });
}

export function fetchProgress(): Promise<ProgressPayload> {
  return requestJson<ProgressPayload>('/api/progress');
}

export function fetchWorkItems(): Promise<WorkItemsPayload> {
  return requestJson<WorkItemsPayload>('/api/work-items');
}

export function fetchGithubIntegration(): Promise<IntegrationStatus> {
  return requestJson<IntegrationStatus>('/api/integrations/github');
}

export function fetchDiscordIntegration(): Promise<IntegrationStatus> {
  return requestJson<IntegrationStatus>('/api/integrations/discord');
}

export function createRoleRequirements(payload: HiringRequest): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/hr/role-requirements', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createInterviewKit(payload: HiringRequest): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/hr/interview-kit', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createOnboardingPlan(payload: HiringRequest): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/hr/onboarding-plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createHandoverBrief(payload: HandoverRequest): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/handover/brief', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createOfficeDocument(payload: OfficeDocumentRequest): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/documents/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchApiKeys(): Promise<{ providers: ApiKeyInfo[] }> {
  return requestJson<{ providers: ApiKeyInfo[] }>('/api/admin/api-keys');
}

export function saveApiKey(payload: {
  provider: string;
  api_key: string;
  model: string;
  base_url: string;
}): Promise<{ ok: boolean; providers: ApiKeyInfo[] }> {
  return requestJson<{ ok: boolean; providers: ApiKeyInfo[] }>(`/api/admin/api-keys/${payload.provider}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteApiKey(provider: string): Promise<{ ok: boolean; providers: ApiKeyInfo[] }> {
  return requestJson<{ ok: boolean; providers: ApiKeyInfo[] }>(`/api/admin/api-keys/${provider}`, {
    method: 'DELETE',
  });
}

export function fetchAccessControl(): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/access-control');
}

export function saveRole(payload: RoleRecord): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/roles', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteRole(roleId: string): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>(`/api/admin/roles/${roleId}`, { method: 'DELETE' });
}

export function saveUser(payload: UserRecord): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteUser(userId: string): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>(`/api/admin/users/${userId}`, { method: 'DELETE' });
}

export function fetchUploads(): Promise<{ uploads: UploadRecord[] }> {
  return requestJson<{ uploads: UploadRecord[] }>('/api/uploads');
}

export async function uploadDocument(formData: FormData): Promise<{ ok: boolean; upload: UploadRecord }> {
  const response = await fetch('/api/uploads', {
    method: 'POST',
    headers: { 'X-PM-User': getCurrentUserId() },
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as { ok: boolean; upload: UploadRecord };
}

export function deleteUpload(uploadId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/uploads/${uploadId}`, { method: 'DELETE' });
}
