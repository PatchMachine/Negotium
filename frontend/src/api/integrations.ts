import { requestJson } from './http';
import type {
  McpAuditRecord,
  McpPromptDescriptor,
  McpResourceDescriptor,
  McpToolDescriptor,
} from './types';

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
