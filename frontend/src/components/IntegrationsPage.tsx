import { useEffect, useState } from 'react';

import {
  fetchDiscordIntegration,
  fetchGithubIntegration,
  fetchMcpHubAudit,
  fetchMcpHubPrompts,
  fetchMcpHubResources,
  fetchMcpHubTools,
  type IntegrationStatus,
  type McpAuditRecord,
  type McpPromptDescriptor,
  type McpResourceDescriptor,
  type McpToolDescriptor,
} from '../api';

export default function IntegrationsPage() {
  const [github, setGithub] = useState<IntegrationStatus | null>(null);
  const [discord, setDiscord] = useState<IntegrationStatus | null>(null);
  const [tools, setTools] = useState<McpToolDescriptor[]>([]);
  const [resources, setResources] = useState<McpResourceDescriptor[]>([]);
  const [prompts, setPrompts] = useState<McpPromptDescriptor[]>([]);
  const [auditRecords, setAuditRecords] = useState<McpAuditRecord[]>([]);

  async function refresh() {
    const [nextGithub, nextDiscord, nextTools, nextResources, nextPrompts, nextAudit] = await Promise.all([
      fetchGithubIntegration(),
      fetchDiscordIntegration(),
      fetchMcpHubTools(),
      fetchMcpHubResources(),
      fetchMcpHubPrompts(),
      fetchMcpHubAudit().catch(() => ({ records: [], count: 0 })),
    ]);
    setGithub(nextGithub);
    setDiscord(nextDiscord);
    setTools(nextTools.tools);
    setResources(nextResources.resources);
    setPrompts(nextPrompts.prompts);
    setAuditRecords(nextAudit.records);
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">MCP integrations</p>
        <h2>MCP 서버 연동</h2>
        <p className="muted">
          패치머신이 외부 플랫폼 양식을 이해하도록 MCP 서버와 플랫폼 커넥터를 관리합니다.
          GitHub/Discord는 기본 커넥터이며, 이후 Notion, Slack, Jira, Google Drive 같은 서버를 추가할 수 있습니다.
        </p>
        <div className="connector-grid">
          <ConnectorCard name="GitHub" description="Issue, PR, Repository 이벤트 양식" status={github} />
          <ConnectorCard name="Discord" description="버그 문의 채널, 스레드, 명령어 양식" status={discord} />
          <ConnectorCard
            name="MCP Tool Hub"
            description={`Tools ${tools.length}개 · Resources ${resources.length}개 · Prompts ${prompts.length}개`}
            status={{ ok: true, configured: tools.length > 0, reason: '', items: [] }}
          />
          <ConnectorCard name="Notion" description="문서/태스크 DB MCP 서버 (준비 중)" status={null} comingSoon />
          <ConnectorCard name="Slack/Jira/Drive" description="추가 업무 플랫폼 MCP 서버 (준비 중)" status={null} comingSoon />
        </div>
      </div>
      <IntegrationPanel title="GitHub Issues" status={github} />
      <IntegrationPanel title="Discord Channels" status={discord} />
      <McpHubPanel tools={tools} resources={resources} prompts={prompts} auditRecords={auditRecords} />
    </section>
  );
}

function ConnectorCard({
  name,
  description,
  status,
  comingSoon = false,
}: {
  name: string;
  description: string;
  status: IntegrationStatus | null;
  comingSoon?: boolean;
}) {
  const label = comingSoon ? '준비 중' : status?.configured ? (status.ok ? '연결됨' : '확인 필요') : '미설정';
  return (
    <article className="connector-card">
      <strong>{name}</strong>
      <p>{description}</p>
      <span className="status-pill">{label}</span>
    </article>
  );
}

function McpHubPanel({
  tools,
  resources,
  prompts,
  auditRecords,
}: {
  tools: McpToolDescriptor[];
  resources: McpResourceDescriptor[];
  prompts: McpPromptDescriptor[];
  auditRecords: McpAuditRecord[];
}) {
  return (
    <div className="panel">
      <p className="eyebrow">MCP-compatible hub</p>
      <h2>PatchOps MCP Hub</h2>
      <p className="muted">
        HTTP-compatible API와 JSON-RPC/SSE skeleton을 함께 제공해 PatchOps Agent가 tools, resources, prompts를 표준 형태로 조회합니다.
      </p>
      <div className="switch-row">
        <span className="status-pill">tools {tools.length}</span>
        <span className="status-pill">resources {resources.length}</span>
        <span className="status-pill">prompts {prompts.length}</span>
      </div>
      <div className="log-list">
        {tools.map((tool) => (
          <article className="log-card" key={tool.name}>
            <strong>{tool.name}</strong>
            <p>{tool.description}</p>
            <small>{tool.server || 'mcp'} · permission: {tool.required_permission}</small>
          </article>
        ))}
      </div>
      <details>
        <summary>Resources</summary>
        <pre>{JSON.stringify(resources.slice(0, 10), null, 2)}</pre>
      </details>
      <details>
        <summary>Prompts</summary>
        <pre>{JSON.stringify(prompts, null, 2)}</pre>
      </details>
      <details>
        <summary>Recent Tool Audit</summary>
        <div className="log-list">
          {auditRecords.map((record) => (
            <article className="log-card" key={record.id}>
              <strong>{record.tool_name}</strong>
              <p>{record.mcp_server} · actor {record.actor || 'unknown'}</p>
              <small>
                risk {record.risk_level}
                {record.guard_findings?.length ? ` · guard ${record.guard_findings.join(', ')}` : ''}
              </small>
            </article>
          ))}
          {!auditRecords.length ? <p className="muted small">아직 MCP tool audit 기록이 없습니다.</p> : null}
        </div>
      </details>
    </div>
  );
}

function IntegrationPanel({ title, status }: { title: string; status: IntegrationStatus | null }) {
  return (
    <div className="panel">
      <p className="eyebrow">Platform connector</p>
      <h2>{title}</h2>
      <p className="muted">
        {status
          ? status.configured
            ? status.ok
              ? '연동 정보 조회 완료'
              : '연동 조회 중 일부 오류가 있습니다.'
            : status.reason
          : '조회 중...'}
      </p>
      <div className="log-list">
        {status?.items.map((item, index) => (
          <article className="log-card" key={`${title}-${index}`}>
            <strong>{String(item.repo || item.channel_name || item.name || item.guild_id || 'item')}</strong>
            <pre>{JSON.stringify(item, null, 2)}</pre>
          </article>
        ))}
      </div>
    </div>
  );
}
