import { requestJson } from './http';
import type {
  AgentPlan,
  AiJobStatus,
  PermanentMemorySource,
  SkillCreateInput,
  SkillDescriptor,
  SkillRunResult,
} from './types';

export function fetchAiJobs(limit = 30): Promise<{ jobs: AiJobStatus[] }> {
  return requestJson<{ jobs: AiJobStatus[] }>(`/api/ai-jobs/recent?limit=${limit}`);
}

export function fetchAiJob(jobId: string): Promise<AiJobStatus> {
  return requestJson<AiJobStatus>(`/api/ai-jobs/${encodeURIComponent(jobId)}`);
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
export function fetchAgentPlans(): Promise<{ plans: AgentPlan[] }> {
  return requestJson<{ plans: AgentPlan[] }>('/api/agent/plans');
}

export function approveAgentPlan(id: string): Promise<{ ok: boolean; plan: AgentPlan }> {
  return requestJson<{ ok: boolean; plan: AgentPlan }>(`/api/agent/plans/${id}/approve`, { method: 'POST' });
}

export function runAgentPlan(id: string): Promise<{ ok: boolean; run: Record<string, unknown> }> {
  return requestJson<{ ok: boolean; run: Record<string, unknown> }>(`/api/agent/plans/${id}/run`, { method: 'POST' });
}

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
