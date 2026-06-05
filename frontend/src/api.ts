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

export type LlmProviderName = 'vllm' | 'openai' | 'anthropic' | 'gemini' | 'together' | 'fake';
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
  together_model: string;
  task_routes: Record<string, LlmTaskRoute>;
};

export type ChatResponse = {
  answer: string;
  route: LlmRuntimeRoute;
  provider: LlmProviderName;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  ai_job?: AiJobStatus;
  skill_id?: string;
  skill_result?: Record<string, unknown>;
  attachment_notes?: string[];
  used_history?: number;
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
  id?: string;
  stage_state?: string;
  runnable?: boolean;
  queue_order?: number;
  source_architecture_id?: string;
  notes?: string;
  owner_id?: string;
  owner_name?: string;
  assignee_kind?: string;
  signed_off_by?: string;
  signed_off_at?: string;
  completion_record?: string;
  priority?: string;
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
  queue_order?: number;
  assignee_kind?: string;
  signed_off_by?: string;
  signed_off_at?: string;
  completion_record?: string;
  created_at?: string;
  updated_at?: string;
};

export type ProcessPlanStep = {
  id: string;
  path: string;
  title: string;
  summary?: string;
  status: string;
  stage_state?: string;
  runnable?: boolean;
  queue_order?: number;
  source_architecture_id?: string;
  notes?: string;
  owner_id?: string;
  owner_name?: string;
  assignee_kind?: string;
  signed_off_by?: string;
  signed_off_at?: string;
  priority?: string;
};

export type ProcessPlan = {
  id: string;
  objective: string;
  architecture_path: string;
  status: 'draft' | 'approved' | 'running' | 'paused' | 'completed' | 'cancelled' | string;
  mode: 'manual' | 'auto' | string;
  approved_by: string;
  approved_at: string;
  created_at: string;
  updated_at: string;
  step_total: number;
  step_done: number;
  steps: ProcessPlanStep[];
  plan_markdown: string;
};

export type WorkArchitecture = {
  title: string;
  markdown: string;
  path: string;
  architecture: Record<string, unknown>;
  queue?: WorkScheduleItem[];
  plan?: ProcessPlan;
  ai_job?: AiJobStatus;
};

export type PermanentMemorySource = {
  id: string;
  kind: string;
  path: string;
  title: string;
  excerpt: string;
  updated_at: string;
};

export type ReadableContextSource = PermanentMemorySource & {
  content: string;
  selected: boolean;
  order: number;
  sensitivity: string;
  origin: string;
};

export type ReadableContextBundle = {
  query: string;
  used_sources: ReadableContextSource[];
  volatile_memories: VolatileMemory[];
  estimated_tokens: number;
  warnings: string[];
  markdown: string;
};

export type AiJobStatus = {
  job_id: string;
  task: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  actor: string;
  input_summary: string;
  used_sources: string[];
  result_path: string;
  error: string;
  created_at: string;
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
  plan_markdown_path?: string;
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

export type PatchArtifactFile = {
  path: string;
  name: string;
  kind: string;
  title: string;
  bytes: number;
  updated_at: string;
  content?: string;
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

export type ContextFirewallDecision = {
  decision: string;
  highest_sensitivity: string;
  sanitized: unknown;
  removed_counts: Record<string, number>;
  blocked_items: string[];
  detectors_triggered: string[];
  audit_id: string;
  redacted_context_hash: string;
  raw_content_stored: boolean;
};

export type ContextFirewallAuditRecord = {
  id: string;
  actor: string;
  agent_run_id: string;
  destination: string;
  task_type: string;
  decision: string;
  highest_sensitivity: string;
  detectors_triggered: string[];
  removed_counts: Record<string, number>;
  blocked_items: string[];
  raw_content_stored: boolean;
  redacted_context_hash: string;
  created_at: string;
};

export type IntegrationStatus = {
  ok: boolean;
  configured: boolean;
  reason: string;
  items: Array<Record<string, unknown>>;
};

export type GitHubConnectorConfig = {
  enabled: boolean;
  allowed_repos: string[];
  trigger_label: string;
  webhook_secret: string;
  app_token: string;
  webhook_secret_present: boolean;
  app_token_present: boolean;
  event_forms: string[];
};

export type DiscordChannelBinding = {
  guild_id: string;
  channel_id: string;
  channel_name: string;
  repo: string;
};

export type DiscordConnectorConfig = {
  enabled: boolean;
  bot_token: string;
  bot_token_present: boolean;
  guild_allowlist: string[];
  channel_bindings: DiscordChannelBinding[];
  command_forms: string[];
};

export type IntegrationConfig = {
  github: GitHubConnectorConfig;
  discord: DiscordConnectorConfig;
};

export type DocumentRead = {
  path: string;
  markdown: string;
  bytes: number;
  modified_at: string;
};

export type ArchiveDocumentListItem = {
  path: string;
  title: string;
  kind: string;
  excerpt: string;
  bytes: number;
  modified_at: string;
};

export type TokenLimit = {
  enforcement_enabled: boolean;
  per_request_max_tokens: number;
  daily_total_tokens: number;
  monthly_total_tokens: number;
};

export type TokenUsageEntry = {
  provider: string;
  model: string;
  task: string;
  actor: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  occurred_at: string;
};

export type TokenUsageSummary = {
  daily_total: number;
  monthly_total: number;
  by_provider: Record<string, number>;
  by_task: Record<string, number>;
  by_actor: Record<string, number>;
  recent: TokenUsageEntry[];
};

export type TokenLimitStatus = {
  limits: TokenLimit;
  usage: TokenUsageSummary;
};

export type HiringRequest = {
  role_title: string;
  business_need: string;
  priority: string;
  department_id?: string;
  position_id?: string;
  candidate_name?: string;
  candidate_profile?: string;
  interview_stage?: string;
  include_workload?: boolean;
};

export type GeneratedDocument = {
  title: string;
  markdown: string;
  path: string;
  ai_job?: AiJobStatus;
  output_format?: string;
  attachment_notes?: string[];
};

export type HandoverRequest = {
  work_title: string;
  outgoing_owner: string;
  incoming_owner: string;
  notes: string;
  generate_tasks?: boolean;
};

export type OfficeDocumentOutputFormat = 'auto' | 'markdown' | 'html' | 'csv' | 'json' | 'text';

export type OfficeDocumentRequest = {
  document_type: 'meeting_minutes' | 'report_draft' | 'work_request' | 'ppt_outline';
  title: string;
  source_text: string;
  audience: string;
  source_ids?: string[];
  query?: string;
  source_limit?: number;
  include_volatile?: boolean;
  token_budget?: number;
  attachment_ids?: string[];
  output_format?: OfficeDocumentOutputFormat;
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

export type HuggingFaceModelItem = {
  id: string;
  downloads: number;
  likes: number;
  tags: string[];
  pipeline_tag: string;
};

export type HuggingFaceModelSearchResult = {
  query: string;
  models: HuggingFaceModelItem[];
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
  department?: string;
  position_id?: string;
};

export type DepartmentRecord = {
  id: string;
  name: string;
  description?: string;
  lead_user_id?: string;
  parent_id?: string;
};

export type PositionRecord = {
  id: string;
  name: string;
  level: number;
  permissions?: string[];
  display_order?: number;
  restrict_title_assignment?: boolean;
  description?: string;
};

export type DepartmentPermissionRecord = {
  department_id: string;
  position_id: string;
  permissions: string[];
};

export type CompanyProfile = {
  organization_size: string;
  industries: string[];
  departments: string[];
  primary_goals: string[];
  data_sensitivity: string[];
  deployment_preference: string;
  company_name: string;
  office_project: string;
  work_summary: string;
  current_tools: string;
  recurring_workflows: string;
  change_management_needs: string;
  automation_priorities: string;
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
  departments: DepartmentRecord[];
  positions: PositionRecord[];
  department_permissions: DepartmentPermissionRecord[];
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
  ai_job?: AiJobStatus;
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

export function createLoginUser(payload: UserRecord & { password: string }): Promise<{ ok: boolean; access_control: AccessControlPayload }> {
  return requestJson<{ ok: boolean; access_control: AccessControlPayload }>('/api/admin/users/create-login', {
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

export function fetchReadableSources(query = '', limit = 100): Promise<{ sources: ReadableContextSource[] }> {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  params.set('limit', String(limit));
  return requestJson<{ sources: ReadableContextSource[] }>(`/api/memory/readable-sources?${params.toString()}`);
}

export function fetchReadableSource(sourceId: string): Promise<ReadableContextSource> {
  return requestJson<ReadableContextSource>(`/api/memory/readable-source?source_id=${encodeURIComponent(sourceId)}`);
}

export function previewReadableContext(payload: {
  query: string;
  source_ids: string[];
  source_limit: number;
  include_volatile: boolean;
  token_budget: number;
}): Promise<ReadableContextBundle> {
  return requestJson<ReadableContextBundle>('/api/memory/readable-context/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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
}): Promise<{ context: Record<string, unknown>; used_sources?: Array<Record<string, unknown>>; volatile_memories?: string[] }> {
  return requestJson<{ context: Record<string, unknown>; used_sources?: Array<Record<string, unknown>>; volatile_memories?: string[] }>('/api/memory/context/compress', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchAiJobs(limit = 30): Promise<{ jobs: AiJobStatus[] }> {
  return requestJson<{ jobs: AiJobStatus[] }>(`/api/ai-jobs/recent?limit=${limit}`);
}

export function fetchAiJob(jobId: string): Promise<AiJobStatus> {
  return requestJson<AiJobStatus>(`/api/ai-jobs/${encodeURIComponent(jobId)}`);
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

export function deleteMemorySource(sourceId: string): Promise<{ ok: boolean; source: PermanentMemorySource; request: DeletionRequest; physical_deleted?: boolean }> {
  return requestJson<{ ok: boolean; source: PermanentMemorySource; request: DeletionRequest; physical_deleted?: boolean }>(
    `/api/memory/sources?source_id=${encodeURIComponent(sourceId)}`,
    { method: 'DELETE' },
  );
}

export function generateAgentPlan(payload: {
  objective: string;
  title: string;
  mode: string;
  schedule_refs: string[];
  memory_refs: string[];
  context?: string;
}): Promise<{ ok: boolean; plan: AgentPlan }> {
  return requestJson<{ ok: boolean; plan: AgentPlan }>('/api/agent/plans/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createPatchRun(payload: {
  repo_id: string;
  request: string;
  autonomy_level?: string;
  privacy_mode?: string;
  target_branch?: string;
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

export function fetchPatchRunFiles(id: string): Promise<{ files: PatchArtifactFile[] }> {
  return requestJson<{ files: PatchArtifactFile[] }>(`/api/patch-runs/${id}/files`);
}

export function readPatchRunFile(id: string, path: string): Promise<{ file: PatchArtifactFile }> {
  return requestJson<{ file: PatchArtifactFile }>(
    `/api/patch-runs/${id}/files/${encodeURIComponent(path)}`,
  );
}

export function savePatchRunPlanMarkdown(id: string, content: string): Promise<{ ok: boolean; patch_run: PatchRun; file: PatchArtifactFile }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; file: PatchArtifactFile }>(`/api/patch-runs/${id}/plan-md`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

export function revisePatchRunPlanMarkdown(
  id: string,
  payload: { instruction: string; current_content?: string; source_refs?: string[] },
): Promise<{ ok: boolean; patch_run: PatchRun; file: PatchArtifactFile }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; file: PatchArtifactFile }>(`/api/patch-runs/${id}/plan-md/revise`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function promotePatchRunPlanMarkdown(
  id: string,
  content = '',
): Promise<{ ok: boolean; patch_run: PatchRun; memory: PermanentMemorySource }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; memory: PermanentMemorySource }>(
    `/api/patch-runs/${id}/plan-md/promote-memory`,
    {
      method: 'POST',
      body: JSON.stringify({ content }),
    },
  );
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

export function applyPatchRunDiff(
  id: string,
  payload: { branch_name?: string; apply?: boolean } = {},
): Promise<{ ok: boolean; patch_run: PatchRun; execution: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; execution: Record<string, unknown> }>(`/api/patch-runs/${id}/apply-diff`, {
    method: 'POST',
    body: JSON.stringify({ arguments: payload }),
  });
}

export function runPatchRunTests(
  id: string,
  payload: { command?: string; dry_run?: boolean } = {},
): Promise<{ ok: boolean; patch_run: PatchRun; test_result: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; test_result: Record<string, unknown> }>(`/api/patch-runs/${id}/run-tests`, {
    method: 'POST',
    body: JSON.stringify({ arguments: payload }),
  });
}

export function analyzePatchRunTestFailure(
  id: string,
  output = '',
): Promise<{ ok: boolean; patch_run: PatchRun; analysis: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; analysis: Record<string, unknown> }>(`/api/patch-runs/${id}/analyze-test-failure`, {
    method: 'POST',
    body: JSON.stringify({ arguments: { output } }),
  });
}

export function draftPatchRunPr(
  id: string,
  payload: { branch_name?: string } = {},
): Promise<{ ok: boolean; patch_run: PatchRun; pr_draft: Record<string, unknown>; memory: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; patch_run: PatchRun; pr_draft: Record<string, unknown>; memory: Record<string, unknown> }>(`/api/patch-runs/${id}/draft-pr`, {
    method: 'POST',
    body: JSON.stringify({ arguments: payload }),
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

export function sanitizeContextFirewall(payload: {
  destination?: string;
  task_type?: string;
  source_uri?: string;
  content: unknown;
}): Promise<{ ok: boolean; result: ContextFirewallDecision }> {
  return requestJson<{ ok: boolean; result: ContextFirewallDecision }>('/api/security/context-firewall/sanitize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchContextFirewallAudit(limit = 50): Promise<{ records: ContextFirewallAuditRecord[]; count: number }> {
  return requestJson<{ records: ContextFirewallAuditRecord[]; count: number }>(`/api/security/context-firewall/audit?limit=${limit}`);
}

export function fetchContextFirewallPolicy(): Promise<{ policy: Record<string, unknown> }> {
  return requestJson<{ policy: Record<string, unknown> }>('/api/security/context-firewall/policy');
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

export function searchHuggingFaceModels(query: string): Promise<HuggingFaceModelSearchResult> {
  return requestJson<HuggingFaceModelSearchResult>('/api/llm/local/huggingface/search', {
    method: 'POST',
    body: JSON.stringify({ query, limit: 12 }),
  });
}

export type ChatSendOptions = {
  task?: string;
  attachmentIds?: string[];
  historyLimit?: number;
};

export function sendChatMessage(
  message: string,
  route: LlmRuntimeRoute,
  provider: LlmProviderName,
  options: string | ChatSendOptions = 'chat',
): Promise<ChatResponse> {
  const opts: ChatSendOptions = typeof options === 'string' ? { task: options } : options;
  return requestJson<ChatResponse>('/api/llm/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      route,
      provider,
      task: opts.task ?? 'chat',
      attachment_ids: opts.attachmentIds ?? [],
      history_limit: opts.historyLimit ?? 8,
    }),
  });
}

export type ChatStreamHandlers = {
  onMeta?: (meta: { route: string; provider: string; model: string; skill_id: string }) => void;
  onDelta?: (text: string) => void;
  onDone?: (response: ChatResponse) => void;
  onError?: (detail: string) => void;
};

/**
 * Stream a chat completion over SSE. Returns the final ChatResponse (also
 * delivered via onDone). Falls back gracefully if the stream errors.
 */
export async function streamChatMessage(
  message: string,
  route: LlmRuntimeRoute,
  provider: LlmProviderName,
  handlers: ChatStreamHandlers,
  options: ChatSendOptions = {},
): Promise<void> {
  const response = await fetch('/api/llm/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      message,
      route,
      provider,
      task: options.task ?? 'chat',
      attachment_ids: options.attachmentIds ?? [],
      history_limit: options.historyLimit ?? 8,
    }),
  });
  if (!response.ok || !response.body) {
    const detail = response.body ? await response.text() : `${response.status} ${response.statusText}`;
    handlers.onError?.(detail);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');
      let eventName = 'message';
      const dataLines: string[] = [];
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;
      let parsed: unknown;
      try {
        parsed = JSON.parse(dataLines.join('\n'));
      } catch {
        continue;
      }
      if (eventName === 'meta') handlers.onMeta?.(parsed as never);
      else if (eventName === 'delta') handlers.onDelta?.((parsed as { text: string }).text);
      else if (eventName === 'done') handlers.onDone?.(parsed as ChatResponse);
      else if (eventName === 'error') handlers.onError?.((parsed as { detail: string }).detail);
    }
  }
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

export function runWorkScheduleItem(itemId: string): Promise<{
  ok: boolean;
  item: WorkScheduleItem;
  items: ProgressLog[];
  result_path: string;
  ai_job?: AiJobStatus;
}> {
  return requestJson<{
    ok: boolean;
    item: WorkScheduleItem;
    items: ProgressLog[];
    result_path: string;
    ai_job?: AiJobStatus;
  }>(`/api/work-schedule/items/${itemId}/run`, {
    method: 'POST',
  });
}

export type AssignmentScope = {
  can_assign: boolean;
  scope: 'all' | 'department' | 'none';
  level: number;
  department_ids: string[];
  departments: DepartmentRecord[];
  assignable_users: UserRecord[];
};

export function fetchAssignmentScope(): Promise<AssignmentScope> {
  return requestJson<AssignmentScope>('/api/work-schedule/assignment-scope');
}

export type OrgRoster = {
  users: UserRecord[];
  departments: DepartmentRecord[];
  positions: PositionRecord[];
};

export type HrEvaluationRecord = {
  id: string;
  user_id: string;
  period: string;
  work_item_ids: string[];
  draft: string;
  final_text: string;
  evidence: string;
  created_by: string;
  created_at: string;
  document_path?: string;
  source_refs: string[];
};

export function fetchOrgRoster(): Promise<OrgRoster> {
  return requestJson<OrgRoster>('/api/org/roster');
}

export function signOffWorkItem(
  itemId: string,
  note = '',
): Promise<{
  ok: boolean;
  item: WorkScheduleItem;
  items: ProgressLog[];
  plan?: ProcessPlan;
}> {
  return requestJson<{
    ok: boolean;
    item: WorkScheduleItem;
    items: ProgressLog[];
    plan?: ProcessPlan;
  }>(`/api/work-schedule/items/${itemId}/sign-off`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export function fetchProcessPlans(): Promise<{ items: ProcessPlan[] }> {
  return requestJson<{ items: ProcessPlan[] }>('/api/process-plans');
}

export function fetchProcessPlan(planId: string): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}`);
}

export function approveProcessPlan(planId: string): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/approve`, { method: 'POST' });
}

export function setProcessPlanMode(planId: string, mode: 'manual' | 'auto'): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/mode`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
}

export function pauseProcessPlan(planId: string): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/pause`, { method: 'POST' });
}

export function resumeProcessPlan(planId: string): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/resume`, { method: 'POST' });
}

export function addProcessStep(
  planId: string,
  payload: { title: string; notes?: string; owner_name?: string; priority?: string; assignee_kind?: string },
): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/steps`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProcessStep(
  planId: string,
  stepId: string,
  payload: { title?: string; notes?: string; owner_name?: string; priority?: string; assignee_kind?: string },
): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/steps/${stepId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProcessStep(planId: string, stepId: string): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/steps/${stepId}`, {
    method: 'DELETE',
  });
}

export function reorderProcessSteps(planId: string, orderedIds: string[]): Promise<ProcessPlan> {
  return requestJson<ProcessPlan>(`/api/process-plans/${planId}/reorder`, {
    method: 'POST',
    body: JSON.stringify({ ordered_ids: orderedIds }),
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

export type SkillInputSchema = {
  name: string;
  type: string;
  required: boolean;
  description: string;
};

export type SkillDescriptor = {
  id: string;
  name: string;
  description: string;
  category: string;
  executor: 'prompt' | 'tool' | 'cli';
  required_permission: string;
  risk: string;
  tool: string;
  output_format: string;
  inputs: SkillInputSchema[];
};

export type SkillRunResult = {
  skill_id: string;
  executor: string;
  status: string;
  output_text: string;
  output_path: string;
  output_format: string;
  tool_result: Record<string, unknown>;
  notes: string[];
};

export function fetchSkills(): Promise<{ skills: SkillDescriptor[] }> {
  return requestJson<{ skills: SkillDescriptor[] }>('/api/skills');
}

export function runSkill(
  skillId: string,
  inputs: Record<string, unknown>,
): Promise<{ ok: boolean; result: SkillRunResult }> {
  return requestJson<{ ok: boolean; result: SkillRunResult }>(
    `/api/skills/${encodeURIComponent(skillId)}/run`,
    {
      method: 'POST',
      body: JSON.stringify({ inputs }),
    },
  );
}

export type SkillCreateInput = {
  id: string;
  name: string;
  description?: string;
  instructions?: string;
  category?: string;
  executor?: 'prompt' | 'tool' | 'cli';
  required_permission?: string;
  risk?: string;
  output_format?: string;
  output_folder?: string;
  tool?: string;
  inputs?: SkillInputSchema[];
};

export function createSkill(
  payload: SkillCreateInput,
): Promise<{ ok: boolean; skill: SkillDescriptor; skills: SkillDescriptor[] }> {
  return requestJson<{ ok: boolean; skill: SkillDescriptor; skills: SkillDescriptor[] }>(
    '/api/skills',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
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

export function saveDepartment(payload: DepartmentRecord): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/departments', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteDepartment(departmentId: string): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>(`/api/admin/departments/${departmentId}`, { method: 'DELETE' });
}

export function savePosition(payload: PositionRecord): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/positions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deletePosition(positionId: string): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>(`/api/admin/positions/${positionId}`, { method: 'DELETE' });
}

export function saveDepartmentPermission(payload: DepartmentPermissionRecord): Promise<AccessControlPayload> {
  return requestJson<AccessControlPayload>('/api/admin/department-permissions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchHrEvaluationContext(userId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/api/hr/evaluation/context?user_id=${encodeURIComponent(userId)}`);
}

export function draftHrEvaluation(payload: {
  user_id: string;
  period?: string;
  work_item_ids?: string[];
  criteria?: string;
  notes?: string;
}): Promise<{ ok: boolean; draft: string; context: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; draft: string; context: Record<string, unknown> }>('/api/hr/evaluation/draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function saveHrEvaluation(payload: {
  user_id: string;
  period?: string;
  work_item_ids?: string[];
  criteria?: string;
  notes?: string;
  draft?: string;
  final_text?: string;
  evidence?: string;
  source_refs?: string[];
}): Promise<{ ok: boolean; record: HrEvaluationRecord; document_path?: string }> {
  return requestJson<{ ok: boolean; record: HrEvaluationRecord; document_path?: string }>('/api/hr/evaluation/save', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchHrEvaluationRecords(userId = ''): Promise<{ records: HrEvaluationRecord[] }> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  return requestJson<{ records: HrEvaluationRecord[] }>(`/api/hr/evaluation/records${query}`);
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

export function fetchIntegrationConfig(): Promise<IntegrationConfig> {
  return requestJson<IntegrationConfig>('/api/integrations/config');
}

export function saveGithubConnector(payload: GitHubConnectorConfig): Promise<IntegrationConfig> {
  return requestJson<IntegrationConfig>('/api/integrations/github', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function saveDiscordConnector(payload: DiscordConnectorConfig): Promise<IntegrationConfig> {
  return requestJson<IntegrationConfig>('/api/integrations/discord', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function readArchiveDocument(path: string): Promise<DocumentRead> {
  return requestJson<DocumentRead>(`/api/archive/documents?path=${encodeURIComponent(path)}`);
}

export function fetchArchiveDocumentIndex(query = '', limit = 200): Promise<{ documents: ArchiveDocumentListItem[] }> {
  return requestJson<{ documents: ArchiveDocumentListItem[] }>(
    `/api/archive/document-index?q=${encodeURIComponent(query)}&limit=${limit}`,
  );
}

export function fetchTokenLimits(): Promise<TokenLimitStatus> {
  return requestJson<TokenLimitStatus>('/api/llm/token-limits');
}

export function saveTokenLimits(payload: TokenLimit): Promise<TokenLimitStatus> {
  return requestJson<TokenLimitStatus>('/api/llm/token-limits', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

