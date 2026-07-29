// All API payload/response types, shared by the domain modules in this directory.

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
  metrics: Record<string, unknown>;
  operations_memory_configured: boolean;
};

export type LlmProviderName = 'vllm' | 'solar' | 'openai' | 'anthropic' | 'gemini' | 'together' | 'fake';

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
  solar_model: string;
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
  conversation_id?: string;
  turn_id?: string;
  tier?: string;
  reasoning?: string;
  tool_invocations?: Record<string, unknown>[];
  ui_components?: UiComponent[];
  pending_approval?: ApprovalRequest | Record<string, never>;
  notes?: string[];
  context?: ContextUsage;
};

/** How much of the model's context window a turn used. */
export type ContextUsage = {
  prompt_tokens: number;
  completion_tokens: number;
  context_window: number;
  used_ratio: number;
  history_turns: number;
  tool_result_tokens: number;
  /** True when the provider reported no usage and this is an estimate. */
  estimated: boolean;
};

export type ConversationSummary = {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  model: string;
  /** Transcript written before conversations were tracked. */
  legacy: boolean;
};

export type ConversationTurn = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  model: string;
  provider: string;
  tool_invocations: Record<string, unknown>[];
  ui_components: UiComponent[];
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
  created_tasks?: WorkScheduleItem[];
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
  generate_tasks?: boolean;
  participants?: string;
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

export type ModelTier = 'agent' | 'reasoning' | 'general' | 'unknown';

/** Capability keys mirror `CAPABILITY_LABELS` in `adapters/llm/catalog.py`. */
export type ModelCapabilities = Record<string, boolean>;

export type ModelProfile = {
  id: string;
  tier: ModelTier;
  tier_label: string;
  label: string;
  strength: string;
  context_window: number;
  max_output_tokens: number;
  supports_tools: boolean;
  supports_parallel_tool_calls: boolean;
  hidden_reasoning: boolean;
  reasoning_effort: string;
  source: string;
  capabilities: ModelCapabilities;
  /** Korean labels for features this model cannot do. */
  restricted: string[];
};

export type ProviderModelPayload = {
  provider: string;
  models: string[];
  source: string;
  refreshed_at: string;
  reason: string;
  configured: boolean;
  requires_api_key: boolean;
  /** Index-aligned with `models`. */
  model_profiles?: ModelProfile[];
  tiers?: Partial<Record<ModelTier, string[]>>;
};

export type LlmProviderInfo = {
  provider: string;
  label: string;
  base_url: string;
  base_url_source: string;
  fallback_models: string[];
  fallback_model_profiles?: ModelProfile[];
  tiers?: Partial<Record<ModelTier, string[]>>;
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

export type ChatSendOptions = {
  task?: string;
  attachmentIds?: string[];
  historyLimit?: number;
  /** Continues an existing conversation; the server mints one when omitted. */
  conversationId?: string;
  /** Answers to confirmation cards from a turn that paused on a write tool. */
  approvals?: ToolApprovalDecision[];
  /** Override the server's tier-based decision on whether to offer tools. */
  toolsEnabled?: boolean;
};

export type ToolCallEvent = {
  call_id: string;
  tool: string;
  arguments_preview?: string;
  iteration?: number;
};

export type ToolResultEvent = {
  call_id: string;
  tool: string;
  status: 'executed' | 'denied' | 'error' | 'rejected';
  summary?: Record<string, unknown>;
  risk_level?: string;
  error?: string;
};

export type UiComponent = {
  component: string;
  title?: string;
  mode?: 'inline' | 'panel' | 'route';
  props?: Record<string, unknown>;
  reason?: string;
};

export type ApprovalRequest = {
  approval_id: string;
  call_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  risk_level: string;
  required_permission: string;
  summary_ko: string;
};

export type ToolApprovalDecision = {
  approval_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  decision: 'approve' | 'reject';
};

export type ChatStreamHandlers = {
  onMeta?: (meta: {
    route: string;
    provider: string;
    model: string;
    skill_id: string;
    tier?: string;
  }) => void;
  onDelta?: (text: string) => void;
  onDone?: (response: ChatResponse) => void;
  onError?: (detail: string) => void;
  onReasoning?: (text: string) => void;
  onToolCall?: (event: ToolCallEvent) => void;
  onToolResult?: (event: ToolResultEvent) => void;
  onUiComponent?: (component: UiComponent) => void;
  onApprovalRequest?: (request: ApprovalRequest) => void;
};

/**
 * Stream a chat completion over SSE. Returns the final ChatResponse (also
 * delivered via onDone). Falls back gracefully if the stream errors.
 */

export type AssignmentScope = {
  can_assign: boolean;
  scope: 'all' | 'department' | 'none';
  level: number;
  department_ids: string[];
  departments: DepartmentRecord[];
  assignable_users: UserRecord[];
};

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

export type SetupChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type SetupChatRequest = {
  message: string;
  history?: SetupChatMessage[];
  company_profile?: CompanyProfile;
  draft?: InitialOfficeSetupResult | null;
  approvals?: ToolApprovalDecision[];
  conversation_id?: string;
};

export type SetupChatResponse = {
  answer: string;
  provider: string;
  model: string;
  conversation_id: string;
  tool_invocations: Record<string, unknown>[];
  ui_components: UiComponent[];
  pending_approval: ApprovalRequest | Record<string, never>;
  /** Present once the assistant has proposed a draft to review. */
  result: InitialOfficeSetupResult | null;
  notes: string[];
  ai_job?: AiJobStatus;
};

/** Whether the configured model can drive the conversational wizard. */
export type SetupChatCapability = {
  chat_supported: boolean;
  provider: string;
  model: string;
  tier: ModelTier;
  reasons: string[];
};

/** Automation scheduler config (관리자 설정 → 자동화). */
export type WeeklyReportConfig = {
  enabled: boolean;
  weekday: number; // 0=Mon .. 6=Sun
  time: string; // "HH:MM"
  timezone: string;
};

export type ReminderConfig = {
  enabled: boolean;
  time: string;
  stale_days: number;
};

export type SearchConfig = {
  embeddings_enabled: boolean;
};

export type AutomationConfig = {
  weekly_report: WeeklyReportConfig;
  reminders: ReminderConfig;
  search: SearchConfig;
  webhook_url: string;
};

export type SearchIndexStats = {
  files: number;
  chunks: number;
  embedded: number;
  embed_skipped: number;
  last_embed_run: string;
  embeddings_enabled: boolean;
};

export type AutomationStatus = {
  config: AutomationConfig;
  state: Record<string, string>;
};

export type NotificationItem = {
  id: string;
  user_id: string;
  kind: 'weekly_report' | 'reminder' | 'system';
  title: string;
  body: string;
  link_path: string;
  created_at: string;
  read_by: string[];
};

export type NotificationsPayload = {
  items: NotificationItem[];
  unread: number;
};
