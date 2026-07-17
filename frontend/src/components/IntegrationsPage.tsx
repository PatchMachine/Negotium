import { useEffect, useState } from 'react';

import {
  fetchMcpHubAudit,
  fetchMcpHubPrompts,
  fetchMcpHubResources,
  fetchMcpHubTools,
  type McpAuditRecord,
  type McpPromptDescriptor,
  type McpResourceDescriptor,
  type McpToolDescriptor,
} from '../api';

type IntegrationsPageProps = {
  permissions?: string[];
};

type IntegrationTab = 'mcp' | 'audit';

export default function IntegrationsPage({ permissions = [] }: IntegrationsPageProps) {
  void permissions;
  const [tools, setTools] = useState<McpToolDescriptor[]>([]);
  const [resources, setResources] = useState<McpResourceDescriptor[]>([]);
  const [prompts, setPrompts] = useState<McpPromptDescriptor[]>([]);
  const [auditRecords, setAuditRecords] = useState<McpAuditRecord[]>([]);
  const [activeTab, setActiveTab] = useState<IntegrationTab>('mcp');

  async function refresh() {
    const [nextTools, nextResources, nextPrompts, nextAudit] = await Promise.all([
      fetchMcpHubTools(),
      fetchMcpHubResources(),
      fetchMcpHubPrompts(),
      fetchMcpHubAudit().catch(() => ({ records: [], count: 0 })),
    ]);
    setTools(nextTools.tools);
    setResources(nextResources.resources);
    setPrompts(nextPrompts.prompts);
    setAuditRecords(nextAudit.records);
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="page-workspace">
      <div className="workspace-hero">
        <div className="panel">
          <p className="eyebrow">MCP integrations</p>
          <h2>MCP 서버 연동</h2>
          <p className="muted">
            네고티움의 스킬·에이전트 계획·공개 사례 도구를 MCP 표준(tools/resources/prompts)으로
            노출합니다. 외부 MCP 클라이언트가 이 허브를 통해 오피스 업무 도구를 호출할 수 있습니다.
          </p>
        </div>
        <div className="compact-stat-strip">
          <div className="compact-stat">
            <strong>{tools.length}</strong>
            <span>MCP tools</span>
          </div>
          <div className="compact-stat">
            <strong>{auditRecords.length}</strong>
            <span>Recent audits</span>
          </div>
        </div>
      </div>

      <nav className="workspace-tabs" aria-label="MCP integrations sections">
        {([
          ['mcp', 'MCP Hub'],
          ['audit', 'Audit'],
        ] as const).map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            className={activeTab === tab ? 'workspace-tab active' : 'workspace-tab'}
            onClick={() => setActiveTab(tab)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === 'mcp' ? <McpHubPanel tools={tools} resources={resources} prompts={prompts} /> : null}
      {activeTab === 'audit' ? <McpAuditPanel auditRecords={auditRecords} /> : null}
    </section>
  );
}

function McpHubPanel({
  tools,
  resources,
  prompts,
}: {
  tools: McpToolDescriptor[];
  resources: McpResourceDescriptor[];
  prompts: McpPromptDescriptor[];
}) {
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const visibleTools = normalizedQuery
    ? tools.filter((tool) => `${tool.name} ${tool.description} ${tool.server}`.toLowerCase().includes(normalizedQuery))
    : tools;

  return (
    <div className="panel">
      <div className="sticky-panel-header">
        <p className="eyebrow">MCP-compatible hub</p>
        <h2>Negotium MCP Hub</h2>
        <p className="muted">
          HTTP-compatible API와 JSON-RPC/SSE skeleton을 함께 제공해 외부 클라이언트가 tools, resources,
          prompts를 표준 형태로 조회합니다.
        </p>
        <div className="switch-row">
          <span className="status-pill">tools {tools.length}</span>
          <span className="status-pill">resources {resources.length}</span>
          <span className="status-pill">prompts {prompts.length}</span>
        </div>
        <div className="memory-form row-compact">
          <input
            value={query}
            placeholder="tool 이름, 설명, 서버 검색"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>
      <div className="compact-card-list bounded-list">
        {visibleTools.slice(0, 50).map((tool) => (
          <article className="log-card" key={tool.name}>
            <strong>{tool.name}</strong>
            <p>{tool.description}</p>
            <small>
              {tool.server || 'mcp'} · permission: {tool.required_permission}
            </small>
          </article>
        ))}
        {!visibleTools.length ? <p className="muted small">검색 조건에 맞는 tool이 없습니다.</p> : null}
      </div>
      <details className="advanced-panel">
        <summary>Resources preview</summary>
        <div className="bounded-preview">
          <pre>{JSON.stringify(resources.slice(0, 10), null, 2)}</pre>
        </div>
      </details>
      <details className="advanced-panel">
        <summary>Prompts preview</summary>
        <div className="bounded-preview">
          <pre>{JSON.stringify(prompts, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
}

function McpAuditPanel({ auditRecords }: { auditRecords: McpAuditRecord[] }) {
  return (
    <div className="panel">
      <div className="sticky-panel-header">
        <p className="eyebrow">Recent tool audit</p>
        <h2>MCP 호출 감사</h2>
        <p className="muted">tool 호출, actor, guard finding을 별도 탭에서 확인합니다.</p>
      </div>
      <div className="compact-card-list bounded-list">
        {auditRecords.map((record) => (
          <article className="log-card" key={record.id}>
            <strong>{record.tool_name}</strong>
            <p>
              {record.mcp_server} · actor {record.actor || 'unknown'}
            </p>
            <small>
              risk {record.risk_level}
              {record.guard_findings?.length ? ` · guard ${record.guard_findings.join(', ')}` : ''}
            </small>
          </article>
        ))}
        {!auditRecords.length ? <p className="muted small">아직 MCP tool audit 기록이 없습니다.</p> : null}
      </div>
    </div>
  );
}
