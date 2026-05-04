import { getAuthHeaders } from './auth';

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

export type LlmTaskRoute = {
  route: LlmRuntimeRoute;
  provider: LlmProviderName;
  model: string;
};

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
  task_routes: Record<string, LlmTaskRoute>;
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

export type WorkMemory = {
  goals: string;
  active_projects: string;
  current_focus: string;
  blockers: string;
  decisions: string;
  risks: string;
  next_actions: string;
  updated_at: string;
};

export type WorkScheduleItem = {
  id: string;
  title: string;
  owner_id: string;
  owner_name: string;
  status: string;
  priority: string;
  start_date: string;
  due_date: string;
  dependencies: string[];
  notes: string;
  source_architecture_id: string;
  created_at?: string;
  updated_at?: string;
};

export type WorkArchitecture = {
  title: string;
  markdown: string;
  path: string;
  architecture: Record<string, unknown>;
};

export type PermanentMemorySource = {
  id: string;
  kind: string;
  path: string;
  title: string;
  excerpt: string;
  updated_at: string;
};

export type VolatileMemory = {
  scope: 'global' | 'user' | 'session';
  key: string;
  summary: string;
  current_intent: string;
  active_context: string;
  preferences: string;
  open_questions: string[];
  next_actions: string[];
  relevant_sources: string[];
  expires_at: string;
  updated_at: string;
};

export type ConversationRecord = {
  id: string;
  user_id: string;
  role: string;
  content: string;
  provider: string;
  model: string;
  route: string;
  created_at: string;
};

export type DeletionRequest = {
  id: string;
  requester: string;
  target_type: string;
  target_id: string;
  summary: string;
  source_path: string;
  sensitivity: string;
  reason: string;
  status: string;
};

export type AgentPlan = {
  id: string;
  title: string;
  objective: string;
  mode: string;
  status: string;
  steps: Array<Record<string, unknown>>;
  memory_refs: string[];
  schedule_refs: string[];
};

export type PatchRun = {
  id: string;
  repo_id: string;
  request: string;
  autonomy_level: string;
  privacy_mode: string;
  target_branch: string;
  status: string;
  risk_level: string;
  created_by: string;
  approved_by: string;
  plan: Record<string, unknown>;
  questions: Array<Record<string, unknown>>;
  artifacts: Record<string, unknown>;
  context: Record<string, unknown>;
  constraints: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type PatchEvent = {
  id: string;
  patch_run_id: string;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type IssueCluster = {
  id: string;
  title: string;
  summary: string;
  status: string;
  severity: string;
  canonical_issue_ids: string[];
  source_refs: Array<Record<string, unknown>>;
  affected_repos: string[];
  affected_features: string[];
  confidence: number;
  patch_candidates?: PatchCandidate[];
  test_requirements?: TestRequirement[];
};

export type PatchCandidate = {
  id: string;
  cluster_id: string;
  target_repo: string;
  title: string;
  summary: string;
  risk_level: string;
  status: string;
};

export type TestRequirement = {
  id: string;
  patch_candidate_id: string;
  title: string;
  requirement_type: string;
  given: string;
  when: string;
  then: string;
  priority: string;
  status: string;
  source_refs: string[];
};

export type McpToolDescriptor = {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  inputSchema?: Record<string, unknown>;
  required_permission: string;
  server?: string;
};

export type McpResourceDescriptor = {
  uri: string;
  name: string;
  description: string;
  mimeType: string;
};

export type McpPromptDescriptor = {
  name: string;
  description: string;
  arguments: Array<Record<string, unknown>>;
};

export type McpAuditRecord = {
  id: string;
  actor: string;
  mcp_server: string;
  tool_name: string;
  arguments_redacted: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  risk_level: string;
  policy?: Record<string, unknown>;
  guard_findings?: string[];
  approved_by: string;
  created_at: string;
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
  label?: string;
  configured: boolean;
  masked_value: string;
  model: string;
  base_url: string;
  base_url_source?: string;
};

export type ProviderModelPayload = {
  provider: string;
  models: string[];
  source: string;
  refreshed_at: string;
  reason: string;
  configured: boolean;
  requires_api_key: boolean;
};

export type AuthUser = {
  id: string;
  display_name: string;
  title?: string;
  role_id?: string;
  permissions?: string[];
};

export type AuthSession = {
  token: string;
  user: AuthUser;
};

export type CurrentUser = {
  authenticated: boolean;
  user: AuthUser | null;
};

export type AccountRequest = {
  id: string;
  user_id: string;
  display_name: string;
  title: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  decided_at: string;
  decided_by: string;
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

export type CompanyProfile = {
  organization_size: string;
  industries: string[];
  departments: string[];
  primary_goals: string[];
  data_sensitivity: string[];
  deployment_preference: string;
};

export type PatchNoteRecommendationItem = {
  id?: string;
  name?: string;
  description?: string;
  reason?: string;
  priority?: string;
  enabled?: boolean;
};

export type AccessControlPayload = {
  roles: RoleRecord[];
  users: UserRecord[];
  permissions: string[];
};

export type InitialOfficeSetupResult = {
  operations_memory: Record<string, unknown>;
  work_memory: Record<string, unknown>;
  workspace_profile: Record<string, unknown>;
  recommended_package: string;
  agent_packs: PatchNoteRecommendationItem[];
  templates: PatchNoteRecommendationItem[];
  workflows: PatchNoteRecommendationItem[];
  security_defaults: PatchNoteRecommendationItem[];
  integration_priorities: PatchNoteRecommendationItem[];
  llm_task_routes: Record<string, LlmTaskRoute>;
  first_14_days: string[];
  human_review_required: string[];
  roles: RoleRecord[];
  users: UserRecord[];
  notes: string[];
  warnings: string[];
  questions: string[];
  sensitive_hint: boolean;
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
      ...getAuthHeaders(),
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

export function fetchSetupStatus(): Promise<{ setup_required: boolean }> {
  return requestJson<{ setup_required: boolean }>('/api/auth/setup-status');
}

export function setupAdmin(payload: {
  user_id: string;
  display_name: string;
  password: string;
  title: string;
}): Promise<AuthSession> {
  return requestJson<AuthSession>('/api/auth/setup-admin', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

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

export function applyInitialOfficeSetup(payload: InitialOfficeSetupResult): Promise<{ ok: boolean; access_control: AccessControlPayload }> {
  return requestJson<{ ok: boolean; access_control: AccessControlPayload }>('/api/setup/office/apply', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function login(payload: { user_id: string; password: string }): Promise<AuthSession> {
  return requestJson<AuthSession>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>('/api/auth/logout', { method: 'POST' });
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return requestJson<CurrentUser>('/api/auth/me');
}

export function requestAccount(payload: {
  user_id: string;
  display_name: string;
  title: string;
  password: string;
}): Promise<{ ok: boolean; request: AccountRequest }> {
  return requestJson<{ ok: boolean; request: AccountRequest }>('/api/account-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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

export function fetchWorkMemory(): Promise<WorkMemory> {
  return requestJson<WorkMemory>('/api/work-memory');
}

export function saveWorkMemory(memory: WorkMemory): Promise<WorkMemory> {
  return requestJson<WorkMemory>('/api/work-memory', {
    method: 'PUT',
    body: JSON.stringify(memory),
  });
}

export function fetchPermanentMemory(query = ''): Promise<{ sources: PermanentMemorySource[] }> {
  const path = query ? `/api/memory/permanent/search?q=${encodeURIComponent(query)}` : '/api/memory/permanent/recent';
  return requestJson<{ sources: PermanentMemorySource[] }>(path);
}

export function fetchVolatileMemories(): Promise<{ memories: VolatileMemory[] }> {
  return requestJson<{ memories: VolatileMemory[] }>('/api/memory/volatile');
}

export function refreshVolatileMemory(payload: {
  scope: string;
  key: string;
  query: string;
  source_limit: number;
  source_ids?: string[];
}): Promise<VolatileMemory> {
  return requestJson<VolatileMemory>('/api/memory/volatile/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteVolatileMemory(scope: string, key: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/memory/volatile/${scope}/${key}`, { method: 'DELETE' });
}

export function compressContext(payload: {
  scope: string;
  key: string;
  query: string;
  token_budget: number;
  source_limit: number;
  source_ids?: string[];
  include_volatile?: boolean;
}): Promise<{ context: Record<string, unknown> }> {
  return requestJson<{ context: Record<string, unknown> }>('/api/memory/context/compress', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchConversations(): Promise<{ records: ConversationRecord[] }> {
  return requestJson<{ records: ConversationRecord[] }>('/api/memory/conversations');
}

export function fetchMemorySchema(): Promise<{ schemas: Array<Record<string, unknown>>; proposals: Array<Record<string, unknown>> }> {
  return requestJson<{ schemas: Array<Record<string, unknown>>; proposals: Array<Record<string, unknown>> }>('/api/memory/schema');
}

export function proposeMemorySchema(proposal: Record<string, unknown>): Promise<{ ok: boolean; proposal: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; proposal: Record<string, unknown> }>('/api/memory/schema/propose', {
    method: 'POST',
    body: JSON.stringify({ mode: 'llm_propose_human_approve', proposal }),
  });
}

export function approveMemorySchemaProposal(id: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/memory/schema/proposals/${id}/approve`, { method: 'POST' });
}

export function fetchDeletionRequests(): Promise<{ requests: DeletionRequest[] }> {
  return requestJson<{ requests: DeletionRequest[] }>('/api/memory/deletion-requests');
}

export function requestMemoryDeletion(payload: {
  target_type: string;
  target_id: string;
  summary: string;
  source_path: string;
  sensitivity: string;
  reason: string;
}): Promise<{ ok: boolean; request: DeletionRequest }> {
  return requestJson<{ ok: boolean; request: DeletionRequest }>('/api/memory/deletion-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function approveDeletionRequest(id: string): Promise<{ ok: boolean; request: DeletionRequest }> {
  return requestJson<{ ok: boolean; request: DeletionRequest }>(`/api/memory/deletion-requests/${id}/approve`, { method: 'POST' });
}

export function rejectDeletionRequest(id: string): Promise<{ ok: boolean; request: DeletionRequest }> {
  return requestJson<{ ok: boolean; request: DeletionRequest }>(`/api/memory/deletion-requests/${id}/reject`, { method: 'POST' });
}

export function generateAgentPlan(payload: {
  objective: string;
  title: string;
  mode: string;
  schedule_refs: string[];
  memory_refs: string[];
}): Promise<{ ok: boolean; plan: AgentPlan }> {
  return requestJson<{ ok: boolean; plan: AgentPlan }>('/api/agent/plans/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createPatchRun(payload: {
  repo_id: string;
  request: string;
  autonomy_level: string;
  privacy_mode: string;
  target_branch: string;
  constraints?: Record<string, unknown>;
}): Promise<{ ok: boolean; patch_run: PatchRun }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun }>('/api/patch-runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchPatchRuns(): Promise<{ patch_runs: PatchRun[] }> {
  return requestJson<{ patch_runs: PatchRun[] }>('/api/patch-runs');
}

export function fetchPatchRun(id: string): Promise<{ patch_run: PatchRun; events: PatchEvent[] }> {
  return requestJson<{ patch_run: PatchRun; events: PatchEvent[] }>(`/api/patch-runs/${id}`);
}

export function analyzePatchRun(id: string): Promise<{ ok: boolean; patch_run: PatchRun; events: PatchEvent[] }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; events: PatchEvent[] }>(`/api/patch-runs/${id}/analyze`, {
    method: 'POST',
  });
}

export function approvePatchRunPlan(id: string, decision = 'approve', comment = ''): Promise<{ ok: boolean; patch_run: PatchRun }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun }>(`/api/patch-runs/${id}/approve-plan`, {
    method: 'POST',
    body: JSON.stringify({ decision, comment }),
  });
}

export function draftPatchRunDiff(id: string): Promise<{ ok: boolean; patch_run: PatchRun; events: PatchEvent[] }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; events: PatchEvent[] }>(`/api/patch-runs/${id}/draft-diff`, {
    method: 'POST',
  });
}

export function writePatchRunMemory(id: string): Promise<{ ok: boolean; patch_run: PatchRun; memory: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; memory: Record<string, unknown> }>(`/api/patch-runs/${id}/write-memory`, {
    method: 'POST',
  });
}

export function fetchMcpHubTools(): Promise<{ tools: McpToolDescriptor[]; transport: string; count: number }> {
  return requestJson<{ tools: McpToolDescriptor[]; transport: string; count: number }>('/api/mcp-hub/tools');
}

export function fetchMcpHubResources(): Promise<{ resources: McpResourceDescriptor[]; count: number }> {
  return requestJson<{ resources: McpResourceDescriptor[]; count: number }>('/api/mcp-hub/resources');
}

export function fetchMcpHubPrompts(): Promise<{ prompts: McpPromptDescriptor[]; count: number }> {
  return requestJson<{ prompts: McpPromptDescriptor[]; count: number }>('/api/mcp-hub/prompts');
}

export function fetchMcpHubAudit(limit = 50): Promise<{ records: McpAuditRecord[]; count: number }> {
  return requestJson<{ records: McpAuditRecord[]; count: number }>(`/api/mcp-hub/audit?limit=${limit}`);
}

export function callMcpMemoryTool<T = Record<string, unknown>>(
  tool: string,
  argumentsPayload: Record<string, unknown>,
): Promise<{ ok: boolean; tool: string; result: T }> {
  return requestJson<{ ok: boolean; tool: string; result: T }>(`/api/mcp-hub/tools/${tool}`, {
    method: 'POST',
    body: JSON.stringify({ arguments: argumentsPayload }),
  });
}

export function searchIssueMemory(query: string, limit = 8): Promise<{ clusters: IssueCluster[]; total: number }> {
  return callMcpMemoryTool<{ clusters: IssueCluster[]; total: number }>('memory.search_issues', { query, limit }).then(
    (response) => response.result,
  );
}

export function createIssueMemoryTestRequirement(payload: {
  patch_candidate_id: string;
  title: string;
  requirement_type: string;
  given: string;
  when: string;
  then: string;
  priority: string;
}): Promise<{ test_requirement: TestRequirement }> {
  return callMcpMemoryTool<{ test_requirement: TestRequirement }>('memory.create_test_requirement', payload).then(
    (response) => response.result,
  );
}

export function fetchAgentPlans(): Promise<{ plans: AgentPlan[] }> {
  return requestJson<{ plans: AgentPlan[] }>('/api/agent/plans');
}

export function approveAgentPlan(id: string): Promise<{ ok: boolean; plan: AgentPlan }> {
  return requestJson<{ ok: boolean; plan: AgentPlan }>(`/api/agent/plans/${id}/approve`, { method: 'POST' });
}

export function runAgentPlan(id: string): Promise<{ ok: boolean; run: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; run: Record<string, unknown> }>(`/api/agent/plans/${id}/run`, { method: 'POST' });
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
  task = 'chat',
): Promise<ChatResponse> {
  return requestJson<ChatResponse>('/api/llm/chat', {
    method: 'POST',
    body: JSON.stringify({ message, route, provider, task }),
  });
}

export function fetchProgress(): Promise<ProgressPayload> {
  return requestJson<ProgressPayload>('/api/progress');
}

export function fetchWorkItems(): Promise<WorkItemsPayload> {
  return requestJson<WorkItemsPayload>('/api/work-items');
}

export function generateWorkArchitecture(payload: {
  objective: string;
  scope: string;
  horizon: string;
  participants: string;
  constraints: string;
  use_memory: boolean;
}): Promise<WorkArchitecture> {
  return requestJson<WorkArchitecture>('/api/work-architecture/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchWorkSchedule(): Promise<{ items: WorkScheduleItem[] }> {
  return requestJson<{ items: WorkScheduleItem[] }>('/api/work-schedule');
}

export function createWorkScheduleItem(payload: WorkScheduleItem): Promise<{ ok: boolean; item: WorkScheduleItem; items: WorkScheduleItem[] }> {
  return requestJson<{ ok: boolean; item: WorkScheduleItem; items: WorkScheduleItem[] }>('/api/work-schedule/items', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateWorkScheduleItem(payload: WorkScheduleItem): Promise<{ ok: boolean; item: WorkScheduleItem; items: WorkScheduleItem[] }> {
  return requestJson<{ ok: boolean; item: WorkScheduleItem; items: WorkScheduleItem[] }>(`/api/work-schedule/items/${payload.id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteWorkScheduleItem(itemId: string): Promise<{ ok: boolean; items: WorkScheduleItem[] }> {
  return requestJson<{ ok: boolean; items: WorkScheduleItem[] }>(`/api/work-schedule/items/${itemId}`, {
    method: 'DELETE',
  });
}

export function generateWorkSchedule(payload: {
  objective: string;
  participants: string;
  horizon: string;
  constraints: string;
}): Promise<GeneratedDocument> {
  return requestJson<GeneratedDocument>('/api/work-schedule/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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

export function fetchProviderModels(provider: string): Promise<ProviderModelPayload> {
  return requestJson<ProviderModelPayload>(`/api/llm/providers/${provider}/models`);
}

export function previewProviderModels(provider: string, apiKey: string): Promise<ProviderModelPayload> {
  return requestJson<ProviderModelPayload>(`/api/llm/providers/${provider}/models/preview`, {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function saveApiKey(payload: {
  provider: string;
  api_key: string;
  model: string;
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

export function fetchAccountRequests(): Promise<{ requests: AccountRequest[] }> {
  return requestJson<{ requests: AccountRequest[] }>('/api/admin/account-requests');
}

export function approveAccountRequest(requestId: string): Promise<{ ok: boolean; request: AccountRequest }> {
  return requestJson<{ ok: boolean; request: AccountRequest }>(
    `/api/admin/account-requests/${requestId}/approve`,
    { method: 'POST' },
  );
}

export function rejectAccountRequest(requestId: string): Promise<{ ok: boolean; request: AccountRequest }> {
  return requestJson<{ ok: boolean; request: AccountRequest }>(
    `/api/admin/account-requests/${requestId}/reject`,
    { method: 'POST' },
  );
}

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
    throw new Error(await response.text());
  }
  return (await response.json()) as { ok: boolean; upload: UploadRecord };
}

export function deleteUpload(uploadId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/uploads/${uploadId}`, { method: 'DELETE' });
}
