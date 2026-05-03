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
      <IntegrationPanel title="GitHub Issues" status={github} />
      <IntegrationPanel title="Discord Channels" status={discord} />
    </section>
  );
}

function IntegrationPanel({ title, status }: { title: string; status: IntegrationStatus | null }) {
  return (
    <div className="panel">
      <p className="eyebrow">Live Integration</p>
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
