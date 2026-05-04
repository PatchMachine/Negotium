import { useEffect, useState } from 'react';

import { fetchDiscordIntegration, fetchGithubIntegration, type IntegrationStatus } from '../api';

export default function IntegrationsPage() {
  const [github, setGithub] = useState<IntegrationStatus | null>(null);
  const [discord, setDiscord] = useState<IntegrationStatus | null>(null);

  async function refresh() {
    const [nextGithub, nextDiscord] = await Promise.all([
      fetchGithubIntegration(),
      fetchDiscordIntegration(),
    ]);
    setGithub(nextGithub);
    setDiscord(nextDiscord);
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
          <ConnectorCard name="Notion" description="문서/태스크 DB MCP 서버 (준비 중)" status={null} comingSoon />
          <ConnectorCard name="Slack/Jira/Drive" description="추가 업무 플랫폼 MCP 서버 (준비 중)" status={null} comingSoon />
        </div>
      </div>
      <IntegrationPanel title="GitHub Issues" status={github} />
      <IntegrationPanel title="Discord Channels" status={discord} />
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
